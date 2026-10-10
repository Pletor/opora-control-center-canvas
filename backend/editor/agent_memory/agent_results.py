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


class AgentResults:
    def __init__(self, canvas):
        self.canvas = canvas

    def insert(self, db, project, workspace, record):
        """Called inside the same transaction that updates DesktopV3 state."""
        db.execute(
            "INSERT INTO agent_result_records(id,project_id,workspace_id,node_id,record) VALUES(?,?,?,?,?)",
            (record["id"], project, workspace, record["nodeId"], encode(record)),
        )

    def history(self, project, workspace, node_id, before=None):
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
        page = rows[:PAGE_SIZE]
        return {"items": [redact_deep(json.loads(row["record"])) for row in page],
                "hasMore": len(rows) > PAGE_SIZE,
                "nextBefore": page[-1]["sequence"] if len(rows) > PAGE_SIZE else None}
