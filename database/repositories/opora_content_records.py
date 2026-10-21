"""Scoped content-addressed content records; callers own transactions and native writes."""
import json

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_content_validation import validate_record
from backend.canvas.opora_hub_store import canonical, content_id
from database.schema.opora_content_schema import TABLES

PROPOSAL_LIMIT = 12 * 1024 * 1024
MANIFEST_LIMIT = 8 * 1024 * 1024
PROJECT_LIMIT = 128 * 1024 * 1024


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate content JSON key.")
        result[key] = value
    return result


class ContentRecords:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, scope({"project": project, "workspace": workspace})

    def read(self, record_id, *, manifest=False):
        identifier(record_id)
        table, limit = (TABLES[1], MANIFEST_LIMIT) if manifest else (TABLES[0], PROPOSAL_LIMIT)
        row = self.db.execute(f"SELECT CASE WHEN length(CAST(content AS BLOB))<=? THEN content END"
                              f" FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                              (limit, *self.scope, record_id)).fetchone()
        if row is None:
            raise ValueError("Content record does not exist in this scope.")
        if row[0] is None or not isinstance(row[0], str):
            raise ValueError("Stored content record exceeds its byte bound.")
        try:
            record = json.loads(row[0], object_pairs_hook=_pairs)
            validate_record(record, manifest=manifest)
            if (record.get("id") != record_id or (record["project"], record["workspace"]) != self.scope
                    or content_id({key: value for key, value in record.items() if key != "id"}) != record_id):
                raise ValueError("Content record scope or hash integrity mismatch.")
            return record
        except (KeyError, TypeError, RecursionError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Malformed stored content record.") from error

    def insert(self, record, *, manifest=False):
        if not self.db.in_transaction:
            raise RuntimeError("Content records require a caller transaction.")
        if not isinstance(record, dict) or "id" in record or (record.get("project"), record.get("workspace")) != self.scope:
            raise ValueError("Content record scope is invalid.")
        validate_record(record, manifest=manifest)
        result = {**record, "id": content_id(record)}
        raw = canonical(result)
        limit = MANIFEST_LIMIT if manifest else PROPOSAL_LIMIT
        size = len(raw.encode("utf-8"))
        if size > limit:
            raise ValueError("Content record byte bound exceeded.")
        table = TABLES[1] if manifest else TABLES[0]
        if self.db.execute(f"SELECT 1 FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                           (*self.scope, result["id"])).fetchone():
            existing = self.read(result["id"], manifest=manifest)
            if existing != result:
                raise ValueError("Content record identity conflict.")
            return existing
        used = sum(self.db.execute(f"SELECT COALESCE(SUM(length(CAST(content AS BLOB))),0) FROM {name}"
                                   " WHERE project_id=?", (self.scope[0],)).fetchone()[0] for name in TABLES)
        if used + size > PROJECT_LIMIT:
            raise ValueError("Content project quota exceeded.")
        self.db.execute(f"INSERT INTO {table} VALUES(?,?,?,?)", (*self.scope, result["id"], raw))
        return self.read(result["id"], manifest=manifest)

    def proposals(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Content proposal list bound must be 1 through 100.")
        rows = self.db.execute("SELECT id FROM opora_content_proposals WHERE project_id=? AND workspace_id=?"
                               " ORDER BY json_extract(content,'$.createdAt') DESC,id DESC LIMIT ?",
                               (*self.scope, limit)).fetchall()
        return [self.read(row[0]) for row in rows]

    def accepted(self, proposal_id):
        identifier(proposal_id)
        row = self.db.execute("SELECT id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND proposal_id=?",
                              (*self.scope, proposal_id)).fetchone()
        if not row:
            return None
        from database.repositories.opora_changesets import ChangesetRepository
        record = ChangesetRepository(self.db, *self.scope).read(row[0])
        if record.get("proposalId") != proposal_id or record.get("kind") != "acceptance" or not record.get("contentManifestId"):
            raise ValueError("Content acceptance index integrity mismatch.")
        self.read(record["contentManifestId"], manifest=True)
        return row[0]
