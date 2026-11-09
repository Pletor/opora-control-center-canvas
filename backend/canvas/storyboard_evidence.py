"""Pin mutable storyboard inputs in immutable execution assignments, not a second store."""
from copy import deepcopy
from pathlib import Path

from backend.canvas.graph import digest
from backend.canvas.project_folder import ProjectFolder
from backend.editor.storyboard.storyboard import StoryboardService


def collect(canvas, project, workspace, identifiers, graph):
    service = StoryboardService(canvas)
    cards = {node["id"] for node in graph["nodes"] if node["kind"] in ("node", "sector")}
    result = []
    for identifier in sorted(set(identifiers) & cards):
        value = service.read(project, workspace, identifier)
        result.append({"projectId": project, "workspaceId": workspace, "nodeId": identifier,
            "revision": value["revision"], "digest": digest(value["storyboard"]),
            "storyboard": deepcopy(value["storyboard"]), "acceptance": "captured-at-claim"})
    return result


def validate(canvas, project, workspace, pins):
    service = StoryboardService(canvas)
    for pin in pins:
        _validate_pin(pin, project, workspace, service.read(project, workspace, pin["nodeId"]))


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
    for pin in pins:
        source = folder.storyboard(workspace, pin["nodeId"])
        try:
            value = {"storyboard": StoryboardService._stored(source), "revision": StoryboardService._revision(source)}
            _validate_pin(pin, project, workspace, value)
        except (OSError, TypeError, KeyError) as error:
            raise ValueError("Storyboard evidence source is unavailable.") from error
