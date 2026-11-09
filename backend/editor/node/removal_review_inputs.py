"""Native removal/restore preimages and full effect projections, including workspace history."""
import json
from copy import deepcopy

from backend.canvas.opora_changesets import OporaChangesets
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.node import removal_recovery
from backend.editor.node.removal_projection import removed_state


def workspace_rows(db, project, workspace):
    return [list(r) for r in db.execute(f"SELECT {removal_recovery.WORKSPACE_COLUMNS} FROM agent_workspace_revisions WHERE project_id=? AND workspace_id=? ORDER BY node_id,revision", (project, workspace))]


def observe(canvas, project, workspace, operation, data):
    db = canvas.db_for(project)
    head = OporaChangesets(canvas).repository(project, workspace).head()
    if operation == "remove_item" and data.get("kind") == "project":
        if set(data) != {"kind", "target", "digest", "confirmed"} or data["confirmed"] is not True:
            raise ValueError("Removal requires the exact confirmed native preview.")
        snapshot, preview = canvas.removals.project_plan(project, workspace, data["target"])
        if data["digest"] != preview["digest"]:
            raise ValueError("Project changed after removal preview.")
        return {"operation": operation, "input": data, "acceptedHead": head, "before": snapshot, "preview": preview,
                "after": {"archived": True}, "requiresHuman": True}
    current = canvas.view(project, workspace)
    state = DesktopV3State(canvas).current(project, workspace)
    rows = workspace_rows(db, project, workspace)
    recovery_rows = {table: [list(r) for r in db.execute(f"SELECT * FROM {table} WHERE project_id=? AND workspace_id=? ORDER BY id", (project, workspace))]
                     for table in ("graph_recoveries", "removal_restores")}
    before = {"graph": current["graph"], "state": state, "workspaceRows": rows, "recoveryRows": recovery_rows}
    if operation == "remove_item":
        if set(data) != {"kind", "target", "digest", "confirmed"} or data["confirmed"] is not True:
            raise ValueError("Removal requires the exact confirmed native preview.")
        _, graph, preview = canvas.removals.plan(project, workspace, data["kind"], data["target"])
        if data["digest"] != preview["digest"] or preview["blockedBy"]:
            raise ValueError("Removal preview is stale or blocked by another workspace.")
        edge_ids = sorted({e["id"] for e in current["graph"]["edges"]} - {e["id"] for e in graph["edges"]})
        record = removal_recovery.snapshot(canvas, db, project, workspace, current["graph"], preview["nodeIds"], edge_ids)
        after_state = removed_state(state["state"], preview["nodeIds"], edge_ids)
        after_rows = [r for r in rows if r[2] not in preview["nodeIds"]]
        from backend.canvas.activity_log import HumanRequired
        try:
            canvas.removals.guard("agent", current, graph, preview)
            protected = False
        except HumanRequired:
            protected = True
        detail = {"preview": preview, "recovery": record}
    elif operation == "restore_removed":
        if set(data) != {"recoveryId", "digest"} or current["readOnly"] or data["digest"] != current["digest"]:
            raise ValueError("Restore requires writable scope, recoveryId and current graph digest.")
        row = db.execute("SELECT record,used_at FROM removal_restores WHERE project_id=? AND workspace_id=? AND id=?", (project, workspace, data["recoveryId"])).fetchone()
        if row is None or row["used_at"] is not None:
            raise ValueError("Recovery is missing, foreign or already consumed.")
        record = json.loads(row["record"])
        graph, restored = removal_recovery.merged_graph(current["graph"], record)
        after_state = removal_recovery.restored_state(state["state"], record, graph)
        by_key = {tuple(r[:4]): r for r in rows}
        for r in record["workspaceRows"]:
            if r[2] in restored:
                by_key.setdefault(tuple(r[:4]), r)
        after_rows = sorted(by_key.values(), key=lambda r: (r[2], r[3]))
        detail, protected = {"recovery": record}, False
    elif operation == "graph":
        from backend.canvas.opora_graph_candidate import candidate
        from backend.canvas.protected_fields import protected_changes
        if set(data) != {"graph", "digest", "undo"} or type(data["undo"]) is not bool or data["digest"] != current["digest"]:
            raise ValueError("Graph requires exact snapshot, digest and boolean undo.")
        graph = candidate(canvas, project, workspace, current["graph"], data["graph"], data["undo"])
        after_state, after_rows = state["state"], rows
        detail, protected = {}, bool(protected_changes(current["graph"], graph))
    else:
        raise ValueError("Unknown canvas operation.")
    return {"operation": operation, "input": deepcopy(data), "acceptedHead": head, "before": before,
            "after": {"graph": graph, "state": after_state, "workspaceRows": after_rows},
            "requiresHuman": protected or head is not None, **detail}


def verify(canvas, project, workspace, reviewed, result):
    db = canvas.db_for(project)
    if OporaChangesets(canvas).repository(project, workspace).head() != reviewed["acceptedHead"]:
        raise ValueError("Working operation changed accepted authority unexpectedly.")
    if reviewed.get("preview", {}).get("kind") == "project":
        row = canvas.db.execute("SELECT snapshot FROM archived_projects WHERE project_id=?", (project,)).fetchone()
        if row is None or json.loads(row[0]) != reviewed["before"] or result.get("removedProject") != project:
            raise ValueError("Project archive readback differs from review.")
        return
    actual = {"graph": canvas.view(project, workspace)["graph"],
              "state": DesktopV3State(canvas).current(project, workspace)["state"],
              "workspaceRows": workspace_rows(db, project, workspace)}
    if actual != reviewed["after"]:
        raise ValueError("Native graph/state/workspace readback differs from reviewed effects.")
    if reviewed["operation"] in ("remove_item", "restore_removed"):
        recovery_id = result.get("recoveryId") if reviewed["operation"] == "remove_item" else reviewed["input"]["recoveryId"]
        row = db.execute("SELECT record,used_at FROM removal_restores WHERE project_id=? AND workspace_id=? AND id=?", (project, workspace, recovery_id)).fetchone()
        if row is None or json.loads(row["record"]) != reviewed["recovery"] or (row["used_at"] is not None) != (reviewed["operation"] == "restore_removed"):
            raise ValueError("Native recovery identity/content/consumption readback failed.")
