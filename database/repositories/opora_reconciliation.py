"""Immutable scoped reconciliation records; callers own locks and transactions."""
import json

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.opora_reconciliation_validation import validate
from database.repositories.opora_reconciliation_receipts import validate_receipt


class ReconciliationRepository:
    def __init__(self, db, project, workspace):
        scope({"project": project, "workspace": workspace})
        self.db, self.scope = db, (project, workspace)

    def transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Reconciliation mutation requires caller transaction.")

    def read(self, kind, record_id):
        identifier(record_id)
        row = self.db.execute("SELECT kind,binding_id,created_at,content,event_key FROM opora_reconciliation_records "
                              "WHERE project_id=? AND workspace_id=? AND id=?", (*self.scope, record_id)).fetchone()
        if row is None or row[0] != kind:
            raise ValueError("Reconciliation record does not exist in this scope.")
        try:
            record = validate(kind, json.loads(row[3]))
            if (record.get("id") != record_id or (record["project"], record["workspace"]) != self.scope
                    or content_id({k: v for k, v in record.items() if k != "id"}) != record_id
                    or row[1] != (record_id if kind == "binding" else record["bindingId"])
                    or row[2] != record["createdAt"] or row[4] != record.get("eventKey")):
                raise ValueError("Stored reconciliation hash/scope mismatch.")
            self._links(kind, record)
            return record
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("Malformed stored reconciliation record.") from error

    def insert(self, kind, content):
        self.transaction()
        validate(kind, content)
        if "id" in content or (content["project"], content["workspace"]) != self.scope:
            raise ValueError("Invalid reconciliation scope.")
        self._links(kind, content)
        record_id = content_id(content)
        record = {**content, "id": record_id}
        binding = record_id if kind == "binding" else content["bindingId"]
        self.db.execute("INSERT OR IGNORE INTO opora_reconciliation_records VALUES(?,?,?,?,?,?,?,?)",
                        (*self.scope, record_id, kind, binding, content["createdAt"], canonical(record), content.get("eventKey")))
        return self.read(kind, record_id)

    def _links(self, kind, record):
        if kind == "binding":
            return
        binding = self.read("binding", record["bindingId"])
        if kind == "observation":
            data, pin = record["data"], binding["pr"]
            repo, pr = data["repository"], data["pr"]
            if (repo != {k: binding["repository"][k] for k in ("id", "fullName")}
                    or any(pr[k] != pin[k] for k in ("id", "number"))
                    or pr["baseRef"] != binding["repository"]["baseBranch"]
                    or pr["headRepoId"] not in (None, pin["headRepoId"])):
                raise ValueError("Observation differs from immutable subscription identity.")
        if kind == "event":
            observation = self.read("observation", record["observationId"])
            if observation["bindingId"] != binding["id"]:
                raise ValueError("Transition observation belongs to another subscription.")
            state = {key: observation["data"]["pr"][key] for key in
                     ("state", "headSha", "headRepoId", "draft", "mergedAt", "mergeCommitSha")}
            if record["toState"] != state:
                raise ValueError("Transition state disagrees with its observation.")
            if state["state"] == "merged" and record["eventKey"] != content_id({
                    "repositoryId": binding["repository"]["id"], "prId": binding["pr"]["id"],
                    "mergedAt": state["mergedAt"], "mergeCommitSha": state["mergeCommitSha"]}):
                raise ValueError("Merged transition requires its stable deduplication key.")

    def latest_control(self, binding_id):
        self.read("binding", binding_id)
        row = self.db.execute("SELECT control_id,generation,enabled FROM opora_reconciliation_refs "
                              "WHERE project_id=? AND workspace_id=? AND binding_id=?", (*self.scope, binding_id)).fetchone()
        if not row:
            return None
        record = self.read("control", row[0])
        if (record["bindingId"] != binding_id or record["generation"] != row[1] or record["enabled"] != bool(row[2])):
            raise ValueError("Control projection disagrees with immutable history.")
        return record

    def activate_control(self, content, expected_generation):
        self.transaction()
        previous = self.latest_control(content["bindingId"])
        generation = previous["generation"] if previous else 0
        if (generation != expected_generation or content["generation"] != generation + 1
                or content["parentControlId"] != (previous["id"] if previous else None)):
            raise ValueError("Subscription generation changed; refresh before controlling.")
        record = self.insert("control", content)
        self.db.execute("INSERT INTO opora_reconciliation_refs VALUES(?,?,?,?,?,?) "
                        "ON CONFLICT(project_id,workspace_id,binding_id) DO UPDATE SET "
                        "control_id=excluded.control_id,generation=excluded.generation,enabled=excluded.enabled",
                        (*self.scope, content["bindingId"], record["id"], record["generation"], int(record["enabled"])))
        return record

    def bindings(self, limit=100):
        rows = self.db.execute("SELECT id FROM opora_reconciliation_records WHERE project_id=? AND workspace_id=? "
                              "AND kind='binding' ORDER BY rowid DESC LIMIT ?", (*self.scope, limit)).fetchall()
        return [self.read("binding", row[0]) for row in rows]

    def enabled_for(self, repo_id, pr_id, exclude=None):
        rows = self.db.execute("SELECT binding_id FROM opora_reconciliation_refs WHERE project_id=? AND workspace_id=? "
                              "AND enabled=1", self.scope).fetchall()
        for row in rows:
            binding = self.read("binding", row[0])
            control = self.latest_control(row[0])
            if (control["enabled"] and binding["id"] != exclude and binding["repository"]["id"] == repo_id
                    and binding["pr"]["id"] == pr_id):
                return binding
        return None

    def latest_record(self, kind, binding_id):
        row = self.db.execute("SELECT id FROM opora_reconciliation_records WHERE project_id=? AND workspace_id=? "
                              "AND binding_id=? AND kind=? ORDER BY rowid DESC LIMIT 1", (*self.scope, binding_id, kind)).fetchone()
        return self.read(kind, row[0]) if row else None

    def event_for_key(self, binding_id, event_key):
        row = self.db.execute("SELECT id FROM opora_reconciliation_records WHERE project_id=? AND workspace_id=? "
                              "AND binding_id=? AND kind='event' AND event_key=?", (*self.scope, binding_id, event_key)).fetchone()
        return self.read("event", row[0]) if row else None

    def records(self, kind, binding_id):
        rows = self.db.execute("SELECT id FROM opora_reconciliation_records WHERE project_id=? AND workspace_id=? "
                              "AND binding_id=? AND kind=? ORDER BY rowid DESC", (*self.scope, binding_id, kind)).fetchall()
        return [self.read(kind, row[0]) for row in rows]

    def replay(self, request_id, digest):
        row = self.db.execute("SELECT digest,result FROM opora_reconciliation_requests WHERE project_id=? "
                              "AND workspace_id=? AND request_id=?", (*self.scope, request_id)).fetchone()
        if not row:
            return None
        if row[0] != digest:
            raise ValueError("Request ID already used for a different subscription request.")
        result = validate_receipt(json.loads(row[1]))
        if (self.read("binding", result["binding"]["id"]) != result["binding"]
                or self.read("control", result["control"]["id"]) != result["control"]
                or result["control"]["requestDigest"] != digest or result["control"]["requestId"] != request_id
                or result["control"]["bindingId"] != result["binding"]["id"]):
            raise ValueError("Stored request result disagrees with immutable authority.")
        for key, kind in (("lastObservationId", "observation"), ("lastEventId", "event")):
            if result["job"][key] and self.read(kind, result["job"][key])["bindingId"] != result["binding"]["id"]:
                raise ValueError("Stored request result references another subscription.")
        return result

    def remember(self, request_id, digest, result):
        self.transaction()
        validate_receipt(result)
        self.db.execute("INSERT INTO opora_reconciliation_requests VALUES(?,?,?,?,?)",
                        (*self.scope, request_id, digest, canonical(result)))

    def history(self, binding_id, cursor=0, limit=50):
        self.read("binding", binding_id)
        if type(cursor) is not int or not 0 <= cursor <= 9223372036854775807:
            raise ValueError("Invalid reconciliation history cursor.")
        rows = self.db.execute("SELECT rowid,id,kind FROM opora_reconciliation_records WHERE project_id=? AND workspace_id=? "
                              "AND binding_id=? AND rowid>? ORDER BY rowid LIMIT ?", (*self.scope, binding_id, cursor, limit + 1)).fetchall()
        return {"items": [{"kind": r[2], "record": self.read(r[2], r[1])} for r in rows[:limit]],
                "nextCursor": str(rows[limit - 1][0]) if len(rows) > limit else None}
