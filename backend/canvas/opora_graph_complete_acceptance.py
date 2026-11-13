"""Native content writes join graph acceptance's authoritative SQL transaction."""
from copy import deepcopy

from backend.canvas.graph import digest, encode
from backend.canvas.opora_content_changes import entry_key, index, manifest_entries
from backend.canvas.opora_content_sources import native_empty, normalize_config
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, now
from database.repositories.opora_content_records import ContentRecords


def persist(canvas, db, project, workspace, proposal, documents, specs, *, actor):
    from backend.canvas.authority import acts_as_human
    if not acts_as_human(actor) or not db.in_transaction:
        raise ValueError("Complete content acceptance requires reviewed human transaction.")
    review, effects = proposal["stateEffects"], proposal["contentEffects"]
    # Existing persist_state already applied exactly reviewed cleanup in this transaction.
    current = DesktopV3State(canvas).current(project, workspace)
    if current["state"] != review["after"]:
        raise ValueError("Complete content state preimage changed.")
    after = effects["after"]
    from backend.canvas.opora_execution_guard import state_write
    state_write(db, project, workspace, current["state"], after, proposal["resultGraph"], actor)
    if digest(after) != digest(current["state"]):
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                   (project, workspace, current["revision"] + 1, encode(after), now()))
    base = proposal["contentBase"]
    entries = index(base["entries"] if base["requiresAdoption"] else manifest_entries(specs, proposal["parentRevision"]))
    removed = set(proposal["plan"]["removeNodes"])
    entries = {key: value for key, value in entries.items() if key[1] not in removed}
    for item in effects["documents"]:
        scope = (project, workspace, item["nodeId"])
        store = canvas.specs if item["kind"] == "spec" else canvas.texts
        field = "fields" if item["kind"] == "spec" else "text"
        observed = store.read(scope)
        if observed["revision"] != item["expectedRevision"] or observed[field] != item["before"]:
            raise ValueError("Complete content document changed after review.")
        saved = store.save_in_transaction(scope, item["expectedRevision"], item["value"])
        if item["kind"] == "spec":
            documents[item["nodeId"]] = {"nodeId": item["nodeId"], "ownerWorkspace": workspace,
                                         "revision": saved["revision"], "fields": saved["fields"]}
        else:
            entry = {"kind": "text", "target": item["nodeId"], "field": "text", "ownerWorkspace": workspace,
                     "revision": saved["revision"], "value": saved["text"]}
            entries[entry_key(entry)] = entry
    new_ids = {node["id"] for node in proposal["additions"]["nodes"]}
    # Empty native sources are evidence too. Never adopt unrelated live documents.
    for node in new_ids:
        for key, entry in native_empty(node, workspace).items():
            entries.setdefault(key, entry)
    for node in {node["id"] for node in proposal["resultGraph"]["nodes"]}:
        old = normalize_config(review["before"]["nodes"].get(node))
        proposed = normalize_config(after["nodes"].get(node))
        for field, value in proposed.items():
            if node in new_ids or old[field] != value:
                entry = {"kind": "config", "target": node, "field": field, "ownerWorkspace": workspace,
                         "value": deepcopy(value)}
                entries[entry_key(entry)] = entry
    # No adoption of unrelated live text/configuration. Entries are exactly prior authority + reviewed writes.
    manifest = ContentRecords(db, project, workspace).insert({"schemaVersion": 1, "kind": "content-manifest",
        "project": project, "workspace": workspace, "entries": sorted(entries.values(), key=entry_key)}, manifest=True)
    return {"contentManifestId": manifest["id"]}
