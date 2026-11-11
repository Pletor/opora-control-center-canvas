"""Pin mutable storyboard inputs in immutable execution assignments, not a second store."""
from copy import deepcopy
from pathlib import Path

from backend.canvas.graph import digest
from backend.canvas.project_folder import ProjectFolder
from backend.editor.storyboard.storyboard import StoryboardService


def collect(canvas, project, workspace, identifiers, graph, accepted_revision=None):
    service = StoryboardService(canvas)
    cards = {node["id"] for node in graph["nodes"] if node["kind"] in ("node", "sector")}
    result, manifests = [], {}
    for identifier in sorted(set(identifiers) & cards):
        value = service.read(project, workspace, identifier)
        pin = {"projectId": project, "workspaceId": workspace, "nodeId": identifier,
            "revision": value["revision"], "digest": digest(value["storyboard"]),
            "storyboard": deepcopy(value["storyboard"]), "acceptance": "captured-at-claim"}
        if accepted_revision is not None:
            entry, manifest = _accepted(canvas.db_for(project), project, workspace, accepted_revision, identifier, manifests,
                                         shared=True)
            if entry is not None:
                if entry["revision"] != value["revision"] or entry["value"] != value["storyboard"]:
                    raise ValueError("Storyboard input differs from its accepted revision.")
                pin.update(acceptance="accepted-content", acceptedRevision=accepted_revision, contentManifestId=manifest)
            elif value["revision"] or value["storyboard"] is not None:
                raise ValueError("Storyboard input has no accepted content revision.")
        result.append(pin)
    return result


def validate(canvas, project, workspace, pins):
    service = StoryboardService(canvas)
    manifests = {}
    for pin in pins:
        _validate_pin(pin, project, workspace, service.read(project, workspace, pin["nodeId"]))
        _validate_accepted(canvas.db_for(project), project, workspace, pin, manifests)


# Přijatá revize je neměnná: při sběru (`collect`) se storyboardy jejího manifestu čtou jednou na proces, ne pro
# každou kartu (agent-state Ample se 161 kartami jinak četl revizi 941× a trval přes 2 minuty). Kontrola pinu
# (`validate`) čte dál vždy z databáze, aby změněný kontrakt odhalila.
ACCEPTED = {}


def _accepted(db, project, workspace, revision, node, cache, shared=False):
    from database.repositories.opora_changesets import ChangesetRepository
    from database.repositories.opora_content_records import ContentRecords
    # OP-D1B516.1: klíč je projekt + prostor + revize; jiná revize = jiný klíč, nic se nezneplatňuje.
    key = (project, workspace, revision)
    if revision not in cache:
        if not shared or key not in ACCEPTED:
            accepted = ChangesetRepository(db, project, workspace).read(revision)
            manifest = accepted.get("contentManifestId")
            entries = ContentRecords(db, project, workspace).read(manifest, manifest=True)["entries"] if manifest else []
            ACCEPTED[key] = ({entry["target"]: entry for entry in entries if entry["kind"] == "storyboard"}, manifest)
        cache[revision] = ACCEPTED[key]
    entries, manifest = cache[revision]
    return entries.get(node), manifest


def _validate_accepted(db, project, workspace, pin, cache):
    if pin.get("acceptance") != "accepted-content":
        return  # Historical captured-at-claim evidence keeps its exact original meaning.
    from database.repositories.opora_changesets import ChangesetRepository
    original, manifest = _accepted(db, project, workspace, pin["acceptedRevision"], pin["nodeId"], cache)
    current, _ = _accepted(db, project, workspace, ChangesetRepository(db, project, workspace).head(), pin["nodeId"], cache)
    if (manifest != pin["contentManifestId"] or original is None or original != current
            or original["revision"] != pin["revision"] or original["value"] != pin["storyboard"]):
        raise ValueError("Storyboard accepted contract changed; prepare a new assignment.")


def _validate_pin(pin, project, workspace, value):
    if pin["projectId"] != project or pin["workspaceId"] != workspace or digest(pin["storyboard"]) != pin["digest"]:
        raise ValueError("Storyboard execution pin has an invalid scope or digest.")
    if value["revision"] != pin["revision"] or digest(value["storyboard"]) != pin["digest"]:
        raise ValueError("Storyboard input changed; prepare a new assignment.")


def validate_db(db, project, workspace, pins):
    """Post-report readers resolve the same owned files from the trusted DB handle.

    No request path or source pointer participates in filesystem resolution.
    """
    if not pins:
        return
    main = next((row[2] for row in db.execute("PRAGMA database_list") if row[1] == "main"), None)
    path = Path(main).resolve() if main else None
    if path is None or path.name != "project.sqlite" or path.parent.name != project or path.parent.parent.name != "projects":
        raise ValueError("Storyboard evidence source cannot be resolved from this project database.")
    folder = ProjectFolder(path.parent.parent.parent, project)
    from database.repositories.storyboard_revisions import StoryboardRevisions
    manifests = {}
    for pin in pins:
        source = folder.storyboard(workspace, pin["nodeId"])
        try:
            repo = StoryboardRevisions(db, project, workspace, pin["nodeId"])
            value = repo.read() if repo.latest() is not None else {
                "storyboard": StoryboardService._stored(source), "revision": StoryboardService._revision(source)}
            _validate_pin(pin, project, workspace, value)
            _validate_accepted(db, project, workspace, pin, manifests)
        except (OSError, TypeError, KeyError) as error:
            raise ValueError("Storyboard evidence source is unavailable.") from error
