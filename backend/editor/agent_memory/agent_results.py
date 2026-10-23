"""Immutable output evidence bound to the exact captured assignment, in project.sqlite."""

import json
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.graph import encode, valid_id
from backend.editor.agent_packet.desktop_v3_packets import redact_deep

PAGE_SIZE = 20


def result_record(payload, captured):
    """No version supplied means compatibility output, never a verified binding."""
    version = payload.get("contextVersion")
    return {
        "id": uuid.uuid4().hex, "nodeId": payload["nodeId"],
        "contextVersion": version, "binding": "bound" if version else "legacy-unbound",
        "agent": payload["agent"], "createdAt": now(), "output": payload["output"],
        "specification": captured["specification"] if version else None,
        "verification": "agent-reported; not independently verified",
    }


RESULTS_ENDPOINT = "/api/desktop-v3/agent-results"


def brief_history(history, project, workspace, node_id):
    """Historie výsledků pro node-brief: úplné výstupy agentů, snímek zadání jen odkazem.

    Snímek (`specification`) je kopie zadání celého projektu v okamžiku běhu; u velkého projektu
    má přes 200 kB a v briefu by se opakoval u každého výsledku (měřeno 22. 10.: 3,2 z 3,5 MB
    briefu). Nic se nemaže: úplný záznam zůstává v `agent_result_records` a vrací ho `full`.
    """
    items = []
    for item in history["items"]:
        snapshot = item.get("specification")
        if snapshot is not None:
            item = {**item, "specification": {"omitted": True, "bytes": len(encode(snapshot)),
                                              "contextVersion": item.get("contextVersion")}}
        items.append(item)
    return {**history, "items": items,
            "full": {"endpoint": RESULTS_ENDPOINT, "params": {"project": project, "workspace": workspace, "nodeId": node_id},
                     "note": "Úplné záznamy včetně snímku zadání; starší stránky přes before=nextBefore."}}


class AgentResults:
    def __init__(self, canvas):
        self.canvas = canvas

    def insert(self, db, project, workspace, record):
        """Called inside the same transaction that updates DesktopV3 state."""
        db.execute(
            "INSERT INTO agent_result_records(id,project_id,workspace_id,node_id,record) VALUES(?,?,?,?,?)",
            (record["id"], project, workspace, record["nodeId"], encode(record)),
        )

    def history(self, project, workspace, node_id, before=None, *, current=None):
        if not all(valid_id(value) for value in (project, workspace, node_id)):
            raise ValueError("Neplatný rozsah výsledků agenta.")
        if before is not None and (type(before) is not int or before < 1):
            raise ValueError("Neplatný kurzor výsledků agenta.")
        with self.canvas.reading(project):
            view = self.canvas.view(project, workspace)
            if not any(node["id"] == node_id for node in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            rows = self.canvas.db_for(project).execute(
                "SELECT sequence,record FROM agent_result_records WHERE project_id=? AND workspace_id=?"
                " AND node_id=? AND (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?",
                (project, workspace, node_id, before, before, PAGE_SIZE + 1),
            ).fetchall()
            from backend.editor.agent_packet.specification_context import capture_specification
            if rows and current is None:
                current = capture_specification(self.canvas, project, workspace, node_id)
        page = rows[:PAGE_SIZE]
        from backend.editor.agent_packet.assignment_scope import same_assignment
        items = [redact_deep(json.loads(row["record"])) for row in page]
        return {"items": items,
                "assignmentStatus": {item["id"]: ("unbound" if item.get("binding") != "bound" else
                                     "current" if same_assignment(item, current) else "changed") for item in items},
                "hasMore": len(rows) > PAGE_SIZE,
                "nextBefore": page[-1]["sequence"] if len(rows) > PAGE_SIZE else None}
