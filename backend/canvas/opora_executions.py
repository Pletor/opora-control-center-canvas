"""Server-authoritative execution claims over the existing shared card lease."""
import secrets
import time
import uuid
from contextlib import contextmanager

from backend.canvas import opora_execution_budget_runtime as budget_runtime
from backend.canvas import opora_execution_context as sparse_context
from backend.canvas import opora_lease_events as lease_events
from backend.canvas.canvas_service import now
from backend.canvas.graph import digest
from backend.canvas.opora_execution_budget_clock import (
    BudgetClockConflict,
    freeze,
    rollback_preserving_clock,
)
from backend.canvas.opora_execution_budget_status import status as budget_status
from backend.canvas.opora_execution_budget_status import unavailable as unavailable_budget
from backend.canvas.opora_execution_validation import assignment, validate
from backend.editor.agent_memory.card_leases import MAX_PER_OWNER
from database.repositories.opora_executions import Executions

CLAIM = {"nodeId", "expectedAcceptedHead", "expectedContextVersion", "requestId", "ttlSeconds"}


class OporaExecutions:
    def __init__(self, canvas):
        self.canvas = canvas

    @contextmanager
    def transaction(self, project, workspace):
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    yield Executions(db, project, workspace)
                except BudgetClockConflict as conflict:
                    rollback_preserving_clock(db, project, conflict)
                    raise
                except Exception:
                    rollback_preserving_clock(db, project)
                    raise

    def context(self, project, workspace, node):
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project), self.canvas.steady_reads(project):
            try:
                value = assignment(self.canvas, project, workspace, node)
                budget = budget_status(self.canvas.db_for(project), project, workspace, node, value["acceptedRevision"])
                return {"available": True, "unavailableReason": None, "acceptedHead": value["acceptedRevision"],
                        "contextVersion": value["contextVersion"], "executionProtocolVersion": 2 if budget["enrolled"] else 1,
                        "budget": budget} | ({"available": False, "unavailableReason": budget["blockedReason"]} if budget["blockedReason"] else {})
            except ValueError as exc:
                version,budget=unavailable_budget(self.canvas.db_for(project),project,workspace,node)
                return {"available": False, "unavailableReason": str(exc), "acceptedHead": None, "contextVersion": None,
                        "executionProtocolVersion":version,"budget":budget}

    def claim(self, payload, owner):
        extra = budget_runtime.V2_FIELDS if isinstance(payload, dict) and budget_runtime.V2_FIELDS.intersection(payload) else set()
        extra = extra | sparse_context.claim_fields(payload)
        project, workspace = validate(payload, CLAIM | extra)
        if not isinstance(owner, str) or not owner.strip() or len(owner) > 160:
            raise ValueError("An identified execution owner is required.")
        request_digest = digest(payload)
        with self.transaction(project, workspace) as repo:
            replay = repo.replay(owner, payload["requestId"])
            if replay:
                if replay[0] != request_digest:
                    raise ValueError("Claim request identity was already used for different content.")
                return self.response(repo, replay[1])
            node = payload["nodeId"]
            preliminary = budget_runtime.before_claim(repo.db, repo.scope, node, payload, payload["expectedAcceptedHead"], time.time())
            pin = None
            if payload.get("contextProtocolVersion") == 2:
                captured, pin = sparse_context.collect(self.canvas, repo.db, project, workspace, node)
            else:
                captured = assignment(self.canvas, project, workspace, node)
            if (captured["acceptedRevision"] != payload["expectedAcceptedHead"]
                    or captured["contextVersion"] != payload["expectedContextVersion"]):
                raise ValueError("Accepted assignment changed before claim.")
            stamp = time.time()
            lease = repo.db.execute("SELECT expires_at FROM card_leases"
                                    " WHERE project_id=? AND workspace_id=? AND node_id=?",
                                    (project, workspace, node)).fetchone()
            if lease and lease[0] > stamp:
                raise ValueError("Card already has an active lease.")
            if lease:  # The expired lease is replaced now: that is the point the expiry is recorded.
                lease_events.expired(repo, node, owner)
            count = repo.db.execute("SELECT COUNT(*) FROM card_leases"
                                    " WHERE project_id=? AND workspace_id=? AND owner=? AND expires_at>?",
                                    (project, workspace, owner, stamp)).fetchone()[0]
            if count >= MAX_PER_OWNER:
                raise ValueError("Execution owner already holds the maximum number of cards.")
            record = {"executionId": uuid.uuid4().hex, "project": project, "workspace": workspace,
                      "nodeId": node, "token": secrets.token_hex(32), "epoch": repo.next_epoch(node),
                      "acceptedRevision": captured["acceptedRevision"], "assignmentDigest": digest(captured),
                      "assignment": captured, "expiresAt": stamp + payload["ttlSeconds"], "state": "running"}
            record["createdAt"] = now()
            if preliminary is not None:
                record["executionProtocolVersion"] = 2
                record["budget"] = budget_runtime.allocate(repo.db, repo.scope, node, captured["acceptedRevision"], preliminary, record["executionId"], stamp)
                record["expiresAt"] = min(record["expiresAt"], record["budget"]["runDeadlineAt"])
            repo.db.execute("INSERT OR REPLACE INTO card_leases VALUES(?,?,?,?,?,?)",
                            (project, workspace, node, owner, record["token"], record["expiresAt"]))
            if pin is not None:
                record["contextProtocolVersion"] = 2
            repo.insert(record, owner, payload["requestId"], request_digest)
            if pin is not None:
                sparse_context.persist(repo, record, pin)
            lease_events.claimed(repo, record, owner)
            return {**record, **sparse_context.public_proof(repo, record), "serverNow": stamp}

    @staticmethod
    def authenticate(record, token, epoch=None):
        if (not isinstance(token, str) or not secrets.compare_digest(record["token"], token)
                or (epoch is not None and record["epoch"] != epoch)):
            raise ValueError("Execution credential or epoch does not match.")

    def lease_valid(self, repo, record):
        lease = repo.db.execute("SELECT token,expires_at FROM card_leases"
                                " WHERE project_id=? AND workspace_id=? AND node_id=?",
                                (*repo.scope, record["nodeId"])).fetchone()
        epoch = repo.db.execute("SELECT epoch FROM opora_execution_epochs"
                                " WHERE project_id=? AND workspace_id=? AND node_id=?",
                                (*repo.scope, record["nodeId"])).fetchone()
        if (record["state"] != "running" or not lease or lease["expires_at"] <= time.time()
                or not secrets.compare_digest(lease["token"], record["token"])
                or not epoch or epoch[0] != record["epoch"]):
            raise ValueError("Execution is no longer authoritative.")

    def active(self, repo, record):
        budget_runtime.check(repo.db, repo.scope, record, time.time())
        self.lease_valid(repo, record)
        if record.get("contextProtocolVersion") == 2:
            from backend.canvas.opora_execution_context_validation import validate_context
            validate_context(self.canvas, repo, record)
        else:
            if "contextProtocolVersion" in record:
                raise ValueError("Unsupported persisted execution context protocol version.")
            current = assignment(self.canvas, *repo.scope, record["nodeId"])
            if digest(current) != record["assignmentDigest"]:
                raise ValueError("Execution assignment changed; claim a new execution.")
        # Capturing context can be slow; authority must still exist after that work.
        self.lease_valid(repo, record)
        budget_runtime.check(repo.db, repo.scope, record, time.time())

    def response(self, repo, record):
        value = {**record, "serverNow": time.time()}
        if record["state"] == "running":
            try:
                self.active(repo, record)
            except BudgetClockConflict as conflict:
                freeze(repo.db, conflict.high_water, repo.scope[0])
                value["state"] = "revoked"
            except ValueError:
                value["state"] = "revoked"
        try:
            value.update(sparse_context.public_proof(repo, record))
        except ValueError:
            value.update(contextValidation=None, state="revoked")
        return value

    def read_assignment(self, identifier, project, workspace, token):
        with self.transaction(project, workspace) as repo:
            record = repo.read(identifier)
            self.authenticate(record, token)
            keys = ("executionId", "project", "workspace", "nodeId", "epoch", "acceptedRevision", "assignmentDigest", "assignment")
            return {key: record[key] for key in keys} | {key: record[key] for key in ("executionProtocolVersion", "budget", "contextProtocolVersion") if key in record}

    def heartbeat(self, identifier, payload):
        project, workspace = validate(payload, {"token", "epoch", "ttlSeconds"})
        with self.transaction(project, workspace) as repo:
            record = repo.read(identifier)
            self.authenticate(record, payload["token"], payload["epoch"])
            self.active(repo, record)
            stamp = time.time()
            record["expiresAt"] = stamp + payload["ttlSeconds"]
            budget_runtime.check(repo.db, repo.scope, record, stamp)
            if record.get("executionProtocolVersion") == 2:
                record["expiresAt"] = min(record["expiresAt"], record["budget"]["runDeadlineAt"])
            changed = repo.db.execute("UPDATE card_leases SET expires_at=?"
                                     " WHERE project_id=? AND workspace_id=? AND node_id=? AND token=? AND expires_at>?",
                                     (record["expiresAt"], project, workspace, record["nodeId"], record["token"], stamp)).rowcount
            if changed != 1:
                raise ValueError("Execution expired before renewal.")
            repo.save(record)
            lease_events.heartbeat(repo, record)
            return {**record, **sparse_context.public_proof(repo, record), "serverNow": stamp}

    @staticmethod
    def finish(repo, record, state):
        repo.db.execute("DELETE FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=? AND token=?",
                        (*repo.scope, record["nodeId"], record["token"]))
        record["state"] = state
        repo.save(record)

    def release(self, identifier, payload):
        project, workspace = validate(payload, {"token", "epoch"})
        with self.transaction(project, workspace) as repo:
            record = repo.read(identifier)
            self.authenticate(record, payload["token"], payload["epoch"])
            if record["state"] == "running":
                self.finish(repo, record, "released")
                lease_events.released(repo, record)
            return {"executionId": identifier, "state": record["state"], "serverNow": time.time()}
