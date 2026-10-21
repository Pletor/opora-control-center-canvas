"""Immutable graph records, with scoped content-address checks on every read."""
import json

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_graph_records import validate_record
from backend.canvas.opora_hub_store import canonical, content_id


class GraphProposals:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def read(self, record_id, *, manifest=False):
        identifier(record_id)
        table = "opora_graph_manifests" if manifest else "opora_graph_proposals"
        row = self.db.execute(f"SELECT content FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                              (*self.scope, record_id)).fetchone()
        if row is None:
            raise ValueError("Graph record does not exist in this scope.")
        try:
            record = json.loads(row[0])
            if (not isinstance(record, dict) or record.get("id") != record_id
                    or (record.get("project"), record.get("workspace")) != self.scope
                    or content_id({k: v for k, v in record.items() if k != "id"}) != record_id):
                raise ValueError("Graph record integrity mismatch.")
            validate_record(record, manifest=manifest)
            return record
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid graph record.") from exc

    def insert(self, content, *, manifest=False):
        if not self.db.in_transaction:
            raise RuntimeError("Graph records require an explicit transaction.")
        if "id" in content or (content.get("project"), content.get("workspace")) != self.scope:
            raise ValueError("Invalid graph record scope.")
        validate_record(content, manifest=manifest)
        record = {**content, "id": content_id(content)}
        if manifest:
            self.db.execute("INSERT OR IGNORE INTO opora_graph_manifests VALUES(?,?,?,?)",
                            (*self.scope, record["id"], canonical(record)))
        else:
            self.db.execute("INSERT OR IGNORE INTO opora_graph_proposals VALUES(?,?,?,?,?,?)",
                            (*self.scope, record["id"], content["parentRevision"], content["createdAt"], canonical(record)))
        stored = self.read(record["id"], manifest=manifest)
        if stored != record:
            raise ValueError("Graph record identity conflict.")
        return stored

    def accepted(self, proposal_id):
        rows = self.db.execute("SELECT id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=?"
                               " AND proposal_id=?", (*self.scope, proposal_id)).fetchall()
        if len(rows) > 1:
            raise ValueError("Graph proposal has multiple acceptances.")
        if not rows:
            return None
        from backend.canvas.opora_graph_records import accepted_record
        from database.repositories.opora_changesets import ChangesetRepository
        record = accepted_record(ChangesetRepository(self.db, *self.scope), rows[0][0])
        if record.get("proposalId") != proposal_id or record.get("kind") not in ("graph-baseline", "graph-acceptance"):
            raise ValueError("Graph acceptance index integrity mismatch.")
        return rows[0][0]

    def summaries(self):
        rows = self.db.execute("SELECT id FROM opora_graph_proposals WHERE project_id=? AND workspace_id=?"
                               " ORDER BY created_at DESC,id DESC LIMIT 100", self.scope).fetchall()
        for row in rows:
            item = self.read(row[0])
            yield {**{key: item[key] for key in ("id", "kind", "parentRevision", "subject", "by", "createdAt",
                                                "supersedes", "requiresBaseAdoption")},
                   "accepted": self.accepted(item["id"]) is not None,
                   "nodeCount": len(item["additions"]["nodes"]), "edgeCount": len(item["additions"]["edges"])}
