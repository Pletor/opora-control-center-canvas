"""V2 graph records share immutable proposal storage without changing v1 reads."""
import json

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_graph_change_records import validate_record
from backend.canvas.opora_hub_store import canonical, content_id
from database.repositories.opora_graph_proposals import GraphProposals


class GraphChanges(GraphProposals):
    def read(self, record_id, *, manifest=False):
        identifier(record_id)
        if manifest:
            return super().read(record_id, manifest=True)
        row = self.db.execute("SELECT content FROM opora_graph_proposals WHERE project_id=? AND workspace_id=? AND id=?",
                              (*self.scope, record_id)).fetchone()
        if row is None:
            raise ValueError("Graph record does not exist in this scope.")
        try:
            record = json.loads(row[0])
            if record.get("kind") != "graph-changes":
                return super().read(record_id)
            if (record.get("id") != record_id or (record.get("project"), record.get("workspace")) != self.scope
                    or content_id({k: v for k, v in record.items() if k != "id"}) != record_id):
                raise ValueError("Graph change record integrity mismatch.")
            validate_record(record)
            return record
        except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid graph change record.") from exc

    def insert(self, content, *, manifest=False):
        if manifest or content.get("kind") != "graph-changes":
            return super().insert(content, manifest=manifest)
        if not self.db.in_transaction:
            raise RuntimeError("Graph changes require an explicit transaction.")
        if "id" in content or (content.get("project"), content.get("workspace")) != self.scope:
            raise ValueError("Invalid graph change record scope.")
        validate_record(content)
        record = {**content, "id": content_id(content)}
        self.db.execute("INSERT OR IGNORE INTO opora_graph_proposals VALUES(?,?,?,?,?,?)",
                        (*self.scope, record["id"], content["parentRevision"], content["createdAt"], canonical(record)))
        stored = self.read(record["id"])
        if stored != record:
            raise ValueError("Graph change record identity conflict.")
        return stored
