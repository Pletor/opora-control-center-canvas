"""Sanitized immutable native fixture observations in the existing memory delivery queue."""
import json
import re

from backend.canvas.opora_events import emit_event
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_verification_validation import canonical, digest

SCHEMA = "harness.fixture-memory/1"
BINDING = ("executionId", "epoch", "project", "workspace", "nodeId", "acceptedRevision", "assignmentDigest")
BODY = ("outcome", "checkedClaims", "summary", "artifacts", "paired", "authorityCurrentAtCompletion", "promotionAllowed")
MEANING = ("Historical server-observed accepted-fixture outputs only; not production success or promotion. "
           "Check current native Harness fixture quarantine and exact resource version before reuse.")


def _id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@/+-]{0,199}", value) is not None


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _ref(value):
    return isinstance(value, dict) and set(value) == {"id", "digest"} and _id(value["id"]) and _sha(value["digest"])


def _payload(db, project, workspace, verification_id, event_id):
    validate({"project": project, "workspace": workspace}, set())
    if not _id(verification_id) or type(event_id) is not int or event_id < 1:
        return None
    row = db.execute("SELECT q.record,r.record,q.digest,r.digest,q.execution_id,q.node_id,q.request_id,r.request_id "
                     "FROM opora_verification_requests q JOIN opora_verification_reports r ON r.verification_id=q.id "
                     "AND r.project_id=q.project_id AND r.workspace_id=q.workspace_id "
                     "WHERE q.id=? AND q.project_id=? AND q.workspace_id=? "
                     "AND length(q.record)<=262144 AND length(r.record)<=262144",
                     (verification_id, project, workspace)).fetchone()
    if row is None:
        return None
    q, r = json.loads(row[0]), json.loads(row[1])
    origin, paired = q["origin"], r["paired"]
    if (q["id"] != verification_id or q["project"] != project or q["workspace"] != workspace
            or q["executionId"] != row[4] or q["nodeId"] != row[5] or q["requestId"] != row[6]
            or r["requestId"] != row[7] or r["requestId"] != q["requestId"]
            or q["domain"] != "harness-fixtures" or q["trust"] != "server-pending"
            or r["trust"] != "server-observed" or q["independentlyVerified"] is not False
            or r["independentlyVerified"] is not True or r["authorityCurrentAtCompletion"] is not True
            or paired["complete"] is not True or paired["cleanupComplete"] is not True
            or r["promotionAllowed"] is not False or r["outcome"] not in ("passed", "failed")
            or any(item["sourceBinding"] != "canvas-verified" or item["currentEligibility"] is not False for item in (q, r))):
        return None
    if (origin["kind"] != "harness-server-verifier" or origin["protocol"] != "harness.server-fixtures/1"
            or set(origin) != {"kind", "protocol", "execution", "plan", "baseline", "candidate", "problem", "image"}
            or set(origin["execution"]) != set(BINDING) or any(origin["execution"][key] != q[key] for key in BINDING)
            or type(q["epoch"]) is not int or type(origin["execution"]["epoch"]) is not int or q["epoch"] < 1
            or any(not _id(q[key]) for key in ("executionId", "nodeId"))
            or not isinstance(q["acceptedRevision"], str) or not re.fullmatch(r"[a-f0-9]{40}", q["acceptedRevision"])
            or not _sha(q["assignmentDigest"]) or not _id(origin["problem"])
            or any(not _ref(origin[key]) for key in ("plan", "baseline", "candidate"))
            or len({origin[key]["id"] for key in ("plan", "baseline", "candidate")}) != 3
            or not isinstance(origin["image"], str) or not re.fullmatch(r"node@sha256:[a-f0-9]{64}", origin["image"])):
        return None
    if (q["requestDigest"] != row[2] or r["reportDigest"] != row[3]
            or q["requestDigest"] != digest({key: value for key, value in origin.items() if key != "kind"})
            or r["reportDigest"] != digest({"request": q["requestDigest"], "report": {key: r[key] for key in BODY}})
            or not isinstance(r["createdAt"], str) or len(r["createdAt"]) > 40
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT[0-9:.]+(?:Z|\+00:00)", r["createdAt"])):
        return None
    payload = {"schema": SCHEMA, "project": project, "workspace": workspace, "executionId": q["executionId"],
               "nodeId": q["nodeId"], "problem": origin["problem"],
               "candidate": {"id": origin["candidate"]["id"], "contentDigest": origin["candidate"]["digest"]},
               "plan": origin["plan"], "baseline": origin["baseline"], "verificationId": verification_id,
               "requestDigest": q["requestDigest"], "reportDigest": r["reportDigest"], "sourceEvent": event_id,
               "at": r["createdAt"], "outcome": r["outcome"], "productionOutcome": "unknown",
               "promotionAllowed": False, "meaning": MEANING}
    return payload if len(canonical(payload)) <= 12000 else None


def _read(db, project, workspace, verification_id, event_id):
    try:
        return _payload(db, project, workspace, verification_id, event_id)
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return None


def enqueue(db, project, workspace, verification_id):
    """Caller owns the transaction: native report, source event and queue fact roll back together."""
    if not db.in_transaction:
        raise ValueError("Fixture memory enqueue requires a source transaction.")
    payload = _read(db, project, workspace, verification_id, 1)
    if payload is None:
        return False
    prior = db.execute("SELECT 1 FROM harness_memory_deliveries WHERE project_id=? AND workspace_id=? "
                       "AND json_extract(payload,'$.schema')=? AND json_extract(payload,'$.verificationId')=? LIMIT 1",
                       (project, workspace, SCHEMA, verification_id)).fetchone()
    if prior:
        return False
    event = emit_event(db, project_id=project, workspace_id=workspace, kind="harness.fixture.observed",
                       node_id=payload["nodeId"], execution_id=payload["executionId"],
                       data={"verificationId": verification_id, "outcome": payload["outcome"]})
    payload["sourceEvent"] = event
    db.execute("INSERT INTO harness_memory_deliveries VALUES(?,?,?,?,?,?,?,'pending',0,0,'',0,'','','')",
               (project, workspace, payload["executionId"], event, payload["candidate"]["id"], payload["nodeId"],
                json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    return True


def current(db, job):
    """Pruning outbox history cannot invalidate an immutable native source fact."""
    try:
        key, payload = job["key"], json.loads(job["payload"])
        if len(key) != 5 or payload.get("schema") != SCHEMA:
            return False
        expected = _read(db, key[0], key[1], payload["verificationId"], key[3])
        return (expected is not None and key[2] == expected["executionId"] and key[4] == expected["candidate"]["id"]
                and job["node"] == expected["nodeId"] and canonical(payload) == canonical(expected))
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return False
