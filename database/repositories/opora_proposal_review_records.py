"""Bounded immutable storage primitives; public repositories own scope-specific CAS."""
import json

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.opora_proposal_review_validation import (
    validate_event,
    validate_policy,
    validate_receipt,
)
from database.schema.opora_proposal_review_schema import RECORD_TABLES

PROJECT_LIMIT = 64 * 1024 * 1024
POLICY_LIMIT = 32 * 1024
EVENT_LIMIT = 64 * 1024
RECEIPT_LIMIT = 32 * 1024
VALIDATORS = dict(zip(RECORD_TABLES, (validate_policy, validate_event, validate_receipt)))
LIMITS = dict(zip(RECORD_TABLES, (POLICY_LIMIT, EVENT_LIMIT, RECEIPT_LIMIT)))


def pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError("Duplicate proposal review JSON key.")
        result[name] = value
    return result


class ReviewRecords:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, scope({"project": project, "workspace": workspace})

    def tx(self):
        if not self.db.in_transaction:
            raise RuntimeError("Proposal review writes require caller transaction.")

    def read_record(self, table, record_id):
        identifier(record_id)
        row = self.db.execute(f"SELECT CASE WHEN length(CAST(content AS BLOB))<=? THEN content END"
                              f" FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                              (LIMITS[table], *self.scope, record_id)).fetchone()
        if row is None or not isinstance(row[0], str):
            raise ValueError("Proposal review record missing, foreign or oversized.")
        try:
            record = json.loads(row[0], object_pairs_hook=pairs)
            VALIDATORS[table](record)
            if ((record["project"], record["workspace"]) != self.scope or record.get("id") != record_id
                    or content_id({key: value for key, value in record.items() if key != "id"}) != record_id):
                raise ValueError("Proposal review record scope or digest mismatch.")
            return record
        except (TypeError, KeyError, UnicodeError, RecursionError, json.JSONDecodeError) as error:
            raise ValueError("Malformed stored proposal review record.") from error

    def encode(self, table, record):
        self.tx()
        if not isinstance(record, dict) or "id" in record or (record.get("project"), record.get("workspace")) != self.scope:
            raise ValueError("Invalid proposal review write scope.")
        VALIDATORS[table](record)
        result = {**record, "id": content_id(record)}
        raw = canonical(result)
        size = len(raw.encode("utf-8"))
        if size > LIMITS[table]:
            raise ValueError("Proposal review record byte limit exceeded.")
        return result, raw, size

    def quota(self, size):
        used = sum(self.db.execute(f"SELECT COALESCE(SUM(length(CAST(content AS BLOB))),0) FROM {table}"
                                   " WHERE project_id=?", (self.scope[0],)).fetchone()[0] for table in RECORD_TABLES)
        if used + size > PROJECT_LIMIT:
            raise ValueError("Proposal review project quota exceeded.")

    def count(self, table, extra="", params=()):
        return self.db.execute(f"SELECT count(*) FROM {table} WHERE project_id=? AND workspace_id=?" + extra,
                               (*self.scope, *params)).fetchone()[0]

    def advance(self, table, field, old, new, *, extra="", params=(), insert_columns="", insert_values=()):
        if old is None:
            columns = "project_id,workspace_id," + insert_columns + field
            values = (*self.scope, *insert_values, new)
            self.db.execute(f"INSERT INTO {table}({columns}) VALUES({','.join('?' for _ in values)})", values)
        else:
            changed = self.db.execute(f"UPDATE {table} SET {field}=? WHERE project_id=? AND workspace_id=? AND {field}=?" + extra,
                                      (new, *self.scope, old, *params))
            if changed.rowcount != 1:
                raise ValueError("Proposal review reference changed.")
