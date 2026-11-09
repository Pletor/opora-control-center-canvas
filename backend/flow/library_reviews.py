"""Registry-native library intent, human review and atomic native application."""
import hashlib
import json
import re
from uuid import uuid4

from backend.canvas.payload_errors import NextStep
from backend.flow import library_operations as operations
from backend.flow.transactions import atomic
from backend.flow.workflows import FlowNotFound, _now


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _record(row):
    return {**json.loads(row["content"]), "status": row["status"],
            "result": json.loads(row["result"]) if row["result"] else None}


def read(service, project, workspace, identifier):
    row = service.db.execute("SELECT * FROM flow_library_reviews WHERE id=? AND project_id=? AND workspace_id=?",
                             (identifier, project, workspace)).fetchone()
    if row is None:
        raise FlowNotFound("Library review is not in this scope.")
    return _record(row)


def listing(service, project, workspace):
    return {"items": [_record(row) for row in service.db.execute(
        "SELECT * FROM flow_library_reviews WHERE project_id=? AND workspace_id=? ORDER BY rowid DESC", (project, workspace))]}


def submit(service, project, workspace, author, operation, data, request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", request_id):
        raise ValueError("A stable requestId is required.")
    data = operations.validate(operation, data)
    who = canonical(author)
    fingerprint = hashlib.sha256(canonical({"operation": operation, "input": data}).encode()).hexdigest()
    with service.graph_lock_for(project), service.lock_for(project), service.registry_lock, atomic(service.db):
        prior = service.db.execute("SELECT * FROM flow_library_reviews WHERE project_id=? AND workspace_id=? AND author=? AND request_id=?",
                                   (project, workspace, who, request_id)).fetchone()
        if prior:
            if prior["request_hash"] != fingerprint:
                raise NextStep("Request ID already describes another library operation.", code="operation_conflict", hint="Reuse the original input or choose another requestId.")
            return _record(prior)
        owner, observed = operations.observe(service, project, workspace, operation, data)
        identifier = "lr_" + uuid4().hex
        content = {"id": identifier, "project": project, "workspace": workspace, "operation": operation,
                   "input": data, "before": observed, "author": author, "createdAt": _now(), "requiresHuman": owner == "human"}
        status, result = "pending", None
        if owner != "human":
            result = operations.readback(service.db, project, operation, operations.apply(service.db, project, operation, data))
            status = "applied"
        service.db.execute("INSERT INTO flow_library_reviews VALUES(?,?,?,?,?,?,?,?,?)",
            (identifier, project, workspace, request_id, who, fingerprint, canonical(content), status,
             canonical(result) if result is not None else None))
        return read(service, project, workspace, identifier)


def decide(service, project, workspace, identifier, action):
    if action not in ("accept", "reject"):
        raise ValueError("Library review action is accept or reject.")
    with service.graph_lock_for(project), service.lock_for(project), service.registry_lock, atomic(service.db):
        review = read(service, project, workspace, identifier)
        desired = "accepted" if action == "accept" else "rejected"
        if review["status"] == desired:
            return review
        if review["status"] != "pending":
            raise NextStep("Library review has already been decided.", code="review_decided", hint="Read the recorded result.")
        result = None
        if action == "accept":
            try:
                _, current = operations.observe(service, project, workspace, review["operation"], review["input"])
            except (ValueError, LookupError) as error:
                raise NextStep("Library inputs changed: " + str(error), code="library_review_stale",
                               hint="Reload the library and prepare a new review; the old review remains unchanged.") from error
            if current != review["before"]:
                raise NextStep("Library inputs changed since preparation.", code="library_review_stale",
                               hint="Reload current inputs and prepare a new review; no changes were applied.")
            result = operations.readback(service.db, project, review["operation"],
                        operations.apply(service.db, project, review["operation"], review["input"]))
        service.db.execute("UPDATE flow_library_reviews SET status=?,result=? WHERE id=?", (desired, canonical(result), identifier))
        return read(service, project, workspace, identifier)
