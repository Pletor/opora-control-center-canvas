"""Explicit public fixture lessons, delivered by the existing project/role memory queue."""
import json
import re
from urllib.parse import urlencode

from backend.canvas.opora_events import emit_event
from backend.canvas.opora_verification_validation import canonical, digest
from backend.integrations.openviking_client import OpenVikingUnavailable
from backend.memory import roles

SCHEMA = "harness.shared-memory/1"
MEANING = ("An intentionally published candidate passed approved fixture evidence across projects. "
           "Try only in a compatible accepted target assignment and verify locally. "
           "Historical fixture evidence is not production success, causal benefit, permission or stable promotion.")


def _publication(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@/+\-]{0,199}", value):
        raise ValueError("Invalid shared publication.")
    return value


def _assessment(canvas, publication):
    try:
        from backend.library.harness_transfer import SharedEligibility
    except ImportError as error:
        raise ValueError("Native shared assessment is not installed.") from error
    return SharedEligibility(canvas).assess({"publication": publication})


def snapshot(canvas, publication):
    assessment = _assessment(canvas, _publication(publication))
    if assessment["eligible"] is not True:
        raise ValueError("Shared evidence is not currently eligible.")
    # The native public projection is the only input; no free text, card content or caller URI.
    keys = ("publication", "candidate", "problem", "policyDigest", "evidenceDigest", "sources",
            "verifiedProjects", "verifiedImages", "environmentBasis", "evidenceBasis")
    body = {"schema": SCHEMA, **{key: assessment[key] for key in keys}, "meaning": MEANING,
            "productionOutcome": "unknown", "promotionAllowed": False, "executionAuthority": False}
    body["lessonDigest"] = digest(body)
    if len(canonical(body)) > 12000:
        raise ValueError("Shared lesson exceeds its bound.")
    return body


def _source(db, lesson):
    source = lesson["sources"][0]
    row = db.execute("SELECT q.execution_id,q.node_id,r.digest FROM opora_verification_requests q "
                     "JOIN opora_verification_reports r ON r.project_id=q.project_id AND r.workspace_id=q.workspace_id "
                     "AND r.verification_id=q.id WHERE q.project_id=? AND q.workspace_id=? AND q.id=?",
                     (source["project"], source["workspace"], source["verificationId"])).fetchone()
    if row is None or row[2] != source["reportDigest"]:
        raise ValueError("Shared lesson source is unavailable.")
    return row[0], row[1]


def valid_job(db, job):
    """Local queue binding only; cross-project eligibility is checked outside SQL locks."""
    try:
        lesson = json.loads(job["payload"])
        source = lesson["sources"][0]
        execution, node = _source(db, lesson)
        return (lesson["schema"] == SCHEMA and lesson["lessonDigest"] == digest({k: v for k, v in lesson.items() if k != "lessonDigest"})
                and job["key"][:3] == (source["project"], source["workspace"], execution)
                and job["key"][4] == lesson["candidate"]["id"] and job["node"] == node)
    except (ValueError, KeyError, TypeError, IndexError):
        return False


def current(canvas, job):
    try:
        lesson = json.loads(job["payload"])
        return lesson == snapshot(canvas, lesson["publication"])
    except (ValueError, KeyError, TypeError):
        return False


def enqueue(canvas, publication):
    lesson = snapshot(canvas, publication)
    source = lesson["sources"][0]
    project, workspace = source["project"], source["workspace"]
    with canvas.lock_for(project):
        db = canvas.db_for(project)
        with db:
            if db.in_transaction:
                raise ValueError("Shared publication requires its own transaction.")
            db.execute("BEGIN IMMEDIATE")
            execution, node = _source(db, lesson)
            row = db.execute("SELECT state,source_event FROM harness_memory_deliveries WHERE project_id=? AND workspace_id=? "
                             "AND json_extract(payload,'$.schema')=? AND json_extract(payload,'$.lessonDigest')=? LIMIT 1",
                             (project, workspace, SCHEMA, lesson["lessonDigest"])).fetchone()
            if row:
                if row[0] == "superseded":
                    db.execute("UPDATE harness_memory_deliveries SET state='pending',next_attempt=0 WHERE "
                               "project_id=? AND workspace_id=? AND source_event=? AND state='superseded'",
                               (project, workspace, row[1]))
                state = "pending" if row[0] == "superseded" else row[0]
            else:
                event = emit_event(db, project_id=project, workspace_id=workspace, kind="memory.write",
                                   data={"kind": SCHEMA, "publication": publication, "lessonDigest": lesson["lessonDigest"], "state": "queued"})
                db.execute("INSERT INTO harness_memory_deliveries VALUES(?,?,?,?,?,?,?,'pending',0,0,'',0,'','','')",
                           (project, workspace, execution, event, lesson["candidate"]["id"], node, canonical(lesson).decode("utf-8")))
                state = "pending"
    return {"schema": SCHEMA, "publication": publication, "lessonDigest": lesson["lessonDigest"],
            "state": state, "promotionAllowed": False, "meaning": "queued/submitted is not verified readback"}


def recall(canvas, publication):
    from backend.library.harness_memory import memory_uri

    lesson = snapshot(canvas, publication)
    source = lesson["sources"][0]
    with canvas.lock_for(source["project"]):
        row = canvas.db_for(source["project"]).execute(
            "SELECT state,role_id,uri,payload,execution_id,source_event,resource_id,node_id FROM harness_memory_deliveries WHERE project_id=? AND workspace_id=? "
            "AND json_extract(payload,'$.schema')=? AND json_extract(payload,'$.lessonDigest')=? LIMIT 1",
            (source["project"], source["workspace"], SCHEMA, lesson["lessonDigest"])).fetchone()
    memory = getattr(canvas, "memory_service", None)
    if row is None or row[0] != "submitted" or memory is None or not memory.enabled():
        return {"schema": SCHEMA, "status": "unavailable", "publication": publication, "lesson": None}
    if roles.role(row[1]) is None or json.loads(row[3]) != lesson:
        raise ValueError("Shared lesson delivery binding changed.")
    job = {"key": (source["project"], source["workspace"], row[4], row[5], row[6]), "node": row[7], "payload": row[3]}
    with canvas.lock_for(source["project"]):
        if not valid_job(canvas.db_for(source["project"]), job) or row[2] != memory_uri(job, row[1]):
            raise ValueError("Shared lesson URI or source binding changed.")
    # Only the server-owned immutable queue URI, using its original role credential.
    client = memory._role_client(row[1])
    result = client._envelope(client._request("GET", "/api/v1/content/read?" + urlencode({"uri": row[2], "raw": "true"}),
                                           user=row[1], timeout=10))
    text = result.get("content") if isinstance(result, dict) else result
    if not isinstance(text, str) or len(text.encode("utf-8")) > 12000 or json.loads(text) != lesson:
        raise OpenVikingUnavailable("Shared memory readback does not match the published lesson.")
    if snapshot(canvas, publication) != lesson:
        raise ValueError("Shared evidence changed during recall.")
    return {"schema": SCHEMA, "status": "verified-readback", "publication": publication,
            "lesson": lesson, "promotionAllowed": False, "executionAuthority": False}
