import uuid
from datetime import UTC, datetime

from .graph import valid_id

REQUIRED_FIELDS = {
    "project",
    "workspace",
    "nodeId",
    "sourceId",
    "runId",
    "sourceEventId",
    "sourceTimestamp",
    "kind",
    "summary",
}


class AgentActivityJournal:
    """Append-only žurnál bezpečných náhledů aktivity agenta, klíčovaný ID události zdroje.

    Toto NENÍ lidský žurnál (ten vlastní jiný modul); je to jen strojově vyplněný, jen ke
    čtení a k explicitnímu zachycení zdroj -> Canvas, vždy s odlišením času zdroje a
    času příjmu. Nepřepisuje se, jen se doplňuje a deduplikuje podle (source_id, run_id,
    source_event_id).
    """

    def __init__(self, canvas):
        self.canvas = canvas
        canvas.db.execute(
            """CREATE TABLE IF NOT EXISTS agent_activity_entries(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                node_id TEXT NOT NULL, source_id TEXT NOT NULL, run_id TEXT NOT NULL,
                source_event_id TEXT NOT NULL, source_timestamp TEXT, ingest_timestamp TEXT NOT NULL,
                kind TEXT NOT NULL, summary TEXT NOT NULL,
                UNIQUE(source_id, run_id, source_event_id)
            )"""
        )
        canvas.db.commit()

    def capture(self, payload):
        if not isinstance(payload, dict) or set(payload) != REQUIRED_FIELDS:
            raise ValueError("Neplatný formát záznamu aktivity agenta.")
        pid, wid, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        summary = payload["summary"]
        if not isinstance(summary, str) or not summary or len(summary) > 2000:
            raise ValueError("Neplatný náhled aktivity.")
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute("BEGIN IMMEDIATE")
            view = self.canvas.view(pid, wid)
            if not any(n["id"] == node_id for n in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            existing = self.canvas.db.execute(
                """SELECT id,source_timestamp,ingest_timestamp FROM agent_activity_entries
                   WHERE source_id=? AND run_id=? AND source_event_id=?""",
                (payload["sourceId"], payload["runId"], payload["sourceEventId"]),
            ).fetchone()
            if existing is not None:
                return {
                    "entryId": existing["id"],
                    "sourceTimestamp": existing["source_timestamp"],
                    "ingestTimestamp": existing["ingest_timestamp"],
                }
            entry_id = uuid.uuid4().hex
            ingest_timestamp = datetime.now(UTC).isoformat()
            self.canvas.db.execute(
                "INSERT INTO agent_activity_entries VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry_id,
                    pid,
                    wid,
                    node_id,
                    payload["sourceId"],
                    payload["runId"],
                    payload["sourceEventId"],
                    payload["sourceTimestamp"],
                    ingest_timestamp,
                    payload["kind"],
                    summary,
                ),
            )
        return {"entryId": entry_id, "sourceTimestamp": payload["sourceTimestamp"], "ingestTimestamp": ingest_timestamp}

    def list_for_node(self, pid, wid, node_id):
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        with self.canvas.lock:
            self.canvas.view(pid, wid)  # ověří existenci projektu/workspace bez odhalení interních cest
            rows = self.canvas.db.execute(
                """SELECT id,source_id,run_id,source_event_id,source_timestamp,ingest_timestamp,kind,summary
                   FROM agent_activity_entries WHERE project_id=? AND workspace_id=? AND node_id=?
                   ORDER BY ingest_timestamp""",
                (pid, wid, node_id),
            ).fetchall()
        return [
            {
                "entryId": r["id"],
                "sourceId": r["source_id"],
                "runId": r["run_id"],
                "sourceEventId": r["source_event_id"],
                "sourceTimestamp": r["source_timestamp"],
                "ingestTimestamp": r["ingest_timestamp"],
                "kind": r["kind"],
                "summary": r["summary"],
            }
            for r in rows
        ]
