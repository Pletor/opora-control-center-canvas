"""Bounded immutable observer ledger. Transactions belong to the caller."""
from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_execution_observer_auth import strict_json
from backend.canvas.opora_execution_observer_validation import (
    advance,
    intent,
    observation,
    resource_id,
)
from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.opora_review_policy_validation import timestamp
from database.schema.opora_execution_observer_schema import TABLES

PROJECT_LIMIT = 16 * 1024 * 1024
OBSERVATION_LIMIT = 2048
METADATA = {"id", "schemaVersion", "kind", "observerId", "createdAt", "requestDigest", "executionBinding", "providerBinding"}


class ObserverRecords:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, scope({"project": project, "workspace": workspace})

    def read(self, record_id, *, observed=False):
        identifier(record_id)
        table = TABLES[1 if observed else 0]
        row = self.db.execute(f"SELECT CASE WHEN length(CAST(content AS BLOB))<=131072 THEN content END"
                              f" FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                              (*self.scope, record_id)).fetchone()
        if row is None or row[0] is None:
            raise ValueError("Observer evidence is missing in this scope or exceeds its bound.")
        try:
            value = strict_json(row[0])
            body = {key: item for key, item in value.items() if key not in METADATA}
            if not METADATA <= set(value) or value["schemaVersion"] != 1 or type(value["schemaVersion"]) is not int:
                raise ValueError("Invalid observer evidence envelope.")
            (observation(body, check_future=False) if observed else intent(body))
            resource_id(value["observerId"])
            timestamp(value["createdAt"])
            if (value["id"] != record_id or (value["project"], value["workspace"]) != self.scope
                    or content_id({key: item for key, item in value.items() if key != "id"}) != record_id
                    or value["requestDigest"] != digest({"observerId": value["observerId"], "payload": body})
                    or value["kind"] != ("execution-observation" if observed else "execution-intent")
                    or value["executionBinding"] != "canvas-verified" or value["providerBinding"] != "observer-attested"):
                raise ValueError("Observer evidence integrity mismatch.")
            fields = ("intent_id,parent_id,request_id,sequence" if observed else "execution_id,request_id")
            index = self.db.execute(f"SELECT {fields} FROM {table} WHERE id=?", (record_id,)).fetchone()
            expected = ((value["intentId"], value["expectedObservationHead"], value["requestId"], value["sequence"])
                        if observed else (value["executionId"], value["requestId"]))
            if tuple(index) != expected:
                raise ValueError("Observer evidence index integrity mismatch.")
            return value
        except (KeyError, TypeError, RecursionError, UnicodeError) as error:
            raise ValueError("Invalid stored observer evidence.") from error

    def replay(self, payload, observer, *, observed=False):
        table = TABLES[1 if observed else 0]
        clause, args = (("intent_id=? AND request_id=?", (payload["intentId"], payload["requestId"])) if observed
                        else ("request_id=?", (payload["requestId"],)))
        row = self.db.execute(f"SELECT id FROM {table} WHERE project_id=? AND workspace_id=? AND {clause}",
                              (*self.scope, *args)).fetchone()
        if not row:
            return None
        record = self.read(row[0], observed=observed)
        if record["requestDigest"] != digest({"observerId": observer, "payload": payload}):
            raise ValueError("Observer request key was already used for different content.")
        return record

    def head(self, intent_id):
        self.read(intent_id)
        row = self.db.execute("SELECT head_id FROM opora_execution_observation_refs"
                              " WHERE project_id=? AND workspace_id=? AND intent_id=?", (*self.scope, intent_id)).fetchone()
        if row:
            value = self.read(row[0], observed=True)
            if value["intentId"] != intent_id:
                raise ValueError("Observation head scope mismatch.")
            return value
        if self.db.execute("SELECT 1 FROM opora_execution_observations WHERE intent_id=?", (intent_id,)).fetchone():
            raise ValueError("Observation history has lost its head.")
        return None

    def insert(self, payload, observer, created_at, *, observed=False):
        if not self.db.in_transaction:
            raise RuntimeError("Observer writes require a caller transaction.")
        (observation(payload) if observed else intent(payload))
        if (payload["project"], payload["workspace"]) != self.scope:
            raise ValueError("Observer write scope mismatch.")
        existing = self.replay(payload, observer, observed=observed)
        if existing:
            return existing
        resource_id(observer)
        timestamp(created_at)
        previous = self.head(payload["intentId"]) if observed else None
        if observed:
            if payload["expectedObservationHead"] != (previous["id"] if previous else None):
                raise ValueError("Observation head changed.")
            advance(previous, payload)
            if payload["sequence"] > OBSERVATION_LIMIT:
                raise ValueError("Observation history quota exceeded.")
        value = {**payload, "schemaVersion": 1, "kind": "execution-observation" if observed else "execution-intent",
                 "observerId": observer, "createdAt": created_at,
                 "requestDigest": digest({"observerId": observer, "payload": payload}),
                 "executionBinding": "canvas-verified", "providerBinding": "observer-attested"}
        value["id"] = content_id(value)
        raw = canonical(value)
        size = len(raw.encode("utf-8"))
        used = sum(self.db.execute(f"SELECT COALESCE(SUM(length(CAST(content AS BLOB))),0) FROM {table} WHERE project_id=?",
                                   (self.scope[0],)).fetchone()[0] for table in TABLES[:2])
        if size > 131072 or used + size > PROJECT_LIMIT:
            raise ValueError("Observer project evidence quota exceeded.")
        if observed:
            self.db.execute("INSERT INTO opora_execution_observations VALUES(?,?,?,?,?,?,?,?)",
                            (*self.scope, value["id"], payload["intentId"], payload["expectedObservationHead"],
                             payload["requestId"], payload["sequence"], raw))
            if previous:
                self.db.execute("UPDATE opora_execution_observation_refs SET head_id=? WHERE intent_id=? AND head_id=?",
                                (value["id"], payload["intentId"], previous["id"]))
            else:
                self.db.execute("INSERT INTO opora_execution_observation_refs VALUES(?,?,?,?)",
                                (*self.scope, payload["intentId"], value["id"]))
        else:
            self.db.execute("INSERT INTO opora_execution_intents VALUES(?,?,?,?,?,?)",
                            (*self.scope, value["id"], payload["executionId"], payload["requestId"], raw))
        return self.read(value["id"], observed=observed)

    def intents(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Observer list limit must be between one and one hundred.")
        rows = self.db.execute("SELECT id FROM opora_execution_intents WHERE project_id=? AND workspace_id=?"
                               " ORDER BY rowid DESC LIMIT ?", (*self.scope, limit)).fetchall()
        return [self.read(row[0]) for row in rows]
