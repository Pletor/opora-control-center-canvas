"""Accepted content selection includes absent entries and never redacts private evidence."""
from backend.canvas.opora_content_validation import CONFIG_FIELDS
from database.repositories.opora_content_records import ContentRecords


def selected_content(db, project, workspace, revision, card_ids):
    identifier = revision.get("contentManifestId")
    if identifier is None:
        return {"manifestPresent": False}
    manifest = ContentRecords(db, project, workspace).read(identifier, manifest=True)
    accepted = {(item["kind"], item["target"], item["field"]): item for item in manifest["entries"]}
    keys = [("drawing", "", "scene")]
    for target in sorted(card_ids):
        keys.extend([("text", target, "text"), ("drawing", target, "scene")])
        keys.extend(("config", target, field) for field in sorted(CONFIG_FIELDS))
    return {"manifestPresent": True, "entries": [
        {"kind": kind, "target": target, "field": field, "entry": accepted.get((kind, target, field))}
        for kind, target, field in sorted(keys)]}


def require_accepted_content(canvas, project, workspace, head, card_ids, graph):
    from backend.canvas.opora_content_sources import capture_content
    from database.repositories.opora_changesets import ChangesetRepository

    db = canvas.db_for(project)
    record = ChangesetRepository(db, project, workspace).read(head)
    selected = selected_content(db, project, workspace, record, card_ids)
    if not selected["manifestPresent"]:
        return
    entries, _ = capture_content(canvas, project, workspace, graph)
    live = {(item["kind"], item["target"], item["field"]): item for item in entries}
    if any(item["entry"] is None or live.get((item["kind"], item["target"], item["field"])) != item["entry"]
           for item in selected["entries"]):
        raise ValueError("Relevant live content differs from its accepted manifest.")
