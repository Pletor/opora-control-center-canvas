"""Explicit immutable handoff baselines, independent of reported work results."""

import json
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.graph import encode, valid_id
from backend.editor.agent_packet.specification_context import capture_specification
from backend.editor.agent_packet.specification_scope import (
    compatible_capture,
    same_assignment,
    scoped_specification,
)


def save_assignment(canvas, payload):
    if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "nodeId", "contextVersion"}:
        raise ValueError("Předání vyžaduje project, workspace, nodeId a původní contextVersion.")
    project, workspace, node = (payload[key] for key in ("project", "workspace", "nodeId"))
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        captured = capture_specification(canvas, project, workspace, node)
        if canvas.view(project, workspace)["readOnly"]:
            raise ValueError("Pracovní prostor je pouze ke čtení.")
        captured = compatible_capture(canvas, project, workspace, node, payload["contextVersion"], captured)
        if captured is None:
            raise ValueError("Zadání se od načtení změnilo. Načtěte je znovu před předáním.")
        return _insert(canvas, project, workspace, node, captured)


def snapshot_assignment(canvas, project, workspace, node):
    """Snímek zadání při převzetí karty (upgrade-opora #36); volající drží zámky a rozsah ověřil."""
    return _insert(canvas, project, workspace, node, capture_specification(canvas, project, workspace, node))


def _insert(canvas, project, workspace, node, captured):
    record = {"id": uuid.uuid4().hex, "nodeId": node, "createdAt": now(), "binding": "bound", **captured}
    db = canvas.db_for(project)
    with db:
        db.execute("INSERT INTO assignment_snapshots(id,project_id,workspace_id,node_id,record) VALUES(?,?,?,?,?)",
                   (record["id"], project, workspace, node, encode(record)))
    return record


def assignment_comparison(canvas, project, workspace, node_id, identifier, source):
    if source not in ("handoff", "result") or not valid_id(identifier):
        raise ValueError("Neplatná identita předaného zadání.")
    table = "assignment_snapshots" if source == "handoff" else "agent_result_records"
    with canvas.reading(project):
        current = capture_specification(canvas, project, workspace, node_id)
        row = canvas.db_for(project).execute(
            f"SELECT record FROM {table} WHERE id=? AND project_id=? AND workspace_id=? AND node_id=?",
            (identifier, project, workspace, node_id),
        ).fetchone()
        if row is None:
            raise ValueError("Původní zadání v tomto rozsahu neexistuje.")
        original = json.loads(row["record"])
        return {"before": scoped_specification(original.get("specification")), "after": current["specification"],
                "status": "unbound" if not original.get("contextVersion") else
                    "current" if same_assignment(original, current) else "changed"}
