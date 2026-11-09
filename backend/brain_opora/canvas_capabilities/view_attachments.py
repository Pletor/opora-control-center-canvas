"""Explicit human pairing of one browser tab with one live scoped Heart session."""
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime

from backend.canvas.graph import valid_id
from backend.canvas.payload_errors import InvalidPayload, NextStep
from database.repositories.gate_sessions import GateSessionStore

TTL = 60


def conflict(message):
    raise NextStep(message, code="view_attachment_conflict", hint="Attach this tab explicitly to a live Heart session again.")


def scope(service, project, workspace):
    if not valid_id(project) or not valid_id(workspace):
        raise InvalidPayload("Explicit valid project and workspace are required.")
    service.view(project, workspace)


def live(service, project, workspace, identifier):
    if not isinstance(identifier, str) or not valid_id(identifier):
        raise InvalidPayload("A valid Heart session ID is required.")
    session = GateSessionStore(service.db_for(project)).get(identifier)
    stamp = datetime.fromtimestamp(time.time(), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if (session is None or session["project_id"] != project or session["workspace_id"] != workspace
            or session["role"] != "heart" or session["revoked_at"] is not None
            or (session["expires_at"] is not None and session["expires_at"] <= stamp)):
        conflict("The selected Heart session is absent, expired, revoked or outside this scope.")
    return session


def sessions(service, project, workspace):
    scope(service, project, workspace)
    with service.reading(project):
        rows = service.db_for(project).execute("SELECT id,created_at FROM gate_sessions WHERE project_id=? AND workspace_id=? "
            "AND role='heart' AND revoked_at IS NULL ORDER BY created_at DESC", (project, workspace)).fetchall()
        result = []
        for row in rows:
            try:
                live(service, project, workspace, row[0])
                result.append({"sessionId": row[0], "createdAt": row[1]})
            except NextStep:
                continue
        return {"sessions": result}


def _row(db, project, workspace, session):
    return db.execute("SELECT * FROM canvas_view_attachments WHERE project_id=? AND workspace_id=? AND session_id=?",
                      (project, workspace, session)).fetchone()


def attach(service, project, workspace, session):
    scope(service, project, workspace)
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            live(service, project, workspace, session)
            old = _row(db, project, workspace, session)
            if old and old["expires_at"] > time.time():
                conflict("Another tab is already attached to this Heart session.")
            secret, identifier = secrets.token_urlsafe(32), secrets.token_hex(16)
            expires = time.time() + TTL
            db.execute("INSERT OR REPLACE INTO canvas_view_attachments VALUES(?,?,?,?,?,?,NULL,NULL,0)",
                       (project, workspace, session, identifier, hashlib.sha256(secret.encode()).hexdigest(), expires))
            return {"sessionId": session, "attachmentId": identifier, "secret": secret, "expiresAt": expires}


def _authenticate(service, project, workspace, payload):
    session = payload.get("sessionId")
    if not isinstance(session, str):
        raise InvalidPayload("A session ID is required.")
    live(service, project, workspace, session)
    row = _row(service.db_for(project), project, workspace, session)
    secret = payload.get("secret")
    if (not isinstance(secret, str) or not 20 <= len(secret) <= 200 or row is None
            or row["attachment_id"] != payload.get("attachmentId") or row["expires_at"] <= time.time()
            or not hmac.compare_digest(row["secret_hash"], hashlib.sha256(secret.encode()).hexdigest())):
        conflict("This tab attachment is invalid or expired.")
    return row


def act(service, project, workspace, payload, action):
    from backend.brain_opora.canvas_capabilities.session_view import read
    scope(service, project, workspace)
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = _authenticate(service, project, workspace, payload)
            session = row["session_id"]
            if action == "detach":
                db.execute("DELETE FROM canvas_view_attachments WHERE attachment_id=?", (row["attachment_id"],))
                return {"detached": True}
            current = read(service, project, workspace, {"id": session})
            if action == "ack":
                if (type(payload.get("revision")) is not int or payload["revision"] != current["revision"]
                        or type(payload.get("renderEpoch")) is not int or payload["renderEpoch"] != row["render_epoch"]
                        or payload.get("view") != current["view"]):
                    conflict("The rendered view does not match the current requested revision.")
                db.execute("UPDATE canvas_view_attachments SET acknowledged_revision=?,acknowledged_view=? WHERE attachment_id=?",
                           (current["revision"], json.dumps(current["view"]), row["attachment_id"]))
            elif action == "pending":
                db.execute("UPDATE canvas_view_attachments SET acknowledged_revision=NULL,acknowledged_view=NULL,render_epoch=render_epoch+1 WHERE attachment_id=?",
                           (row["attachment_id"],))
            db.execute("UPDATE canvas_view_attachments SET expires_at=? WHERE attachment_id=?",
                       (time.time() + TTL, row["attachment_id"]))
            return {**read(service, project, workspace, {"id": session}),
                    "renderEpoch": _row(db, project, workspace, session)["render_epoch"]}


def status(service, project, workspace, session, revision, view):
    row = _row(service.db_for(project), project, workspace, session)
    if not row or row["expires_at"] <= time.time():
        return {"applied": False, "state": "not_applied", "reason": "No live attached browser tab."}
    try:
        live(service, project, workspace, session)
    except NextStep:
        return {"applied": False, "state": "not_applied", "reason": "Heart session is no longer live."}
    applied = row["acknowledged_revision"] == revision and json.loads(row["acknowledged_view"] or "null") == view
    if applied:
        known = {node["id"] for node in service.view(project, workspace)["graph"]["nodes"]}
        applied = set(view["selection"]) <= known
    return {"applied": applied, "state": "applied" if applied else "awaiting_ui",
            "reason": "Rendered view acknowledged by the attached tab." if applied else "Waiting for this tab to render the current intent."}
