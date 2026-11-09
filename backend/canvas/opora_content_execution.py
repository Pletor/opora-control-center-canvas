"""Accepted content selection includes absent entries and never redacts private evidence."""
from backend.canvas.opora_content_validation import CONFIG_FIELDS
from database.repositories.opora_content_records import ContentRecords


def selected_content(db, project, workspace, revision, card_ids, accepted=None):
    identifier = revision.get("contentManifestId")
    if identifier is None:
        return {"manifestPresent": False}
    if accepted is None:
        accepted = _accepted_entries(db, project, workspace, identifier)
    keys = [("drawing", "", "scene")]
    for target in sorted(card_ids):
        keys.extend([("text", target, "text"), ("drawing", target, "scene")])
        if ("storyboard", target, "storyboard") in accepted:
            keys.append(("storyboard", target, "storyboard"))
        keys.extend(("config", target, field) for field in sorted(CONFIG_FIELDS))
    return {"manifestPresent": True, "entries": [
        {"kind": kind, "target": target, "field": field, "entry": accepted.get((kind, target, field))}
        for kind, target, field in sorted(keys)]}


def _accepted_entries(db, project, workspace, identifier):
    manifest = ContentRecords(db, project, workspace).read(identifier, manifest=True)
    return {(item["kind"], item["target"], item["field"]): item for item in manifest["entries"]}


def _accepted(canvas, project, workspace, head):
    """`(revision, accepted entries | None)` of the accepted head: the same for every card of a steady block."""
    from database.repositories.opora_changesets import ChangesetRepository

    db = canvas.db_for(project)
    record = ChangesetRepository(db, project, workspace).read(head)
    identifier = record.get("contentManifestId")
    return record, None if identifier is None else _accepted_entries(db, project, workspace, identifier)


def _live(canvas, project, workspace, graph):
    from backend.canvas.opora_content_sources import capture_content

    entries, _ = capture_content(canvas, project, workspace, graph)
    return graph, {(item["kind"], item["target"], item["field"]): item for item in entries}


def require_accepted_content(canvas, project, workspace, head, card_ids, graph):
    # Agent-state checks every card against one accepted head and one view graph: read both once per block.
    record, accepted = canvas.steady_value(project, ("accepted_content", workspace, head),
                                           lambda: _accepted(canvas, project, workspace, head))
    selected = selected_content(canvas.db_for(project), project, workspace, record, card_ids, accepted)
    if not selected["manifestPresent"]:
        return
    seen, live = canvas.steady_value(project, ("live_content", workspace),
                                     lambda: _live(canvas, project, workspace, graph))
    if seen is not graph:
        live = _live(canvas, project, workspace, graph)[1]
    if any(item["entry"] is None or live.get((item["kind"], item["target"], item["field"])) != item["entry"]
           for item in selected["entries"]):
        raise ValueError("Relevant live content differs from its accepted manifest.")
