"""Observed GitHub check run `formal/tlc` -> execution-bound verification evidence.

Proofs and model checks run by machine (.github/workflows/formal.yml); nobody reports
them by hand. Whenever the server itself reads a completed `formal/tlc` check run (GitHub
evidence import or the execution-PR loop), this module maps conclusion + head SHA into
the verification store, bound through the execution -> PR link to execution and card.
A PR without a linked execution has no execution identity and is not recorded.

Trust stays `agent-reported`: the workflow is code of the PR under review, so a green
check is an observation, not an independent verifier. `lean` is a declared placeholder
kind that is `not_connected`; a `formal/lean` check is never mapped. Contract:
docs/oporahub-verification.md. Callers own locks and the SQLite transaction.
"""
import hashlib
import json
import logging
import uuid

from backend.canvas import opora_verification_validation as validation
from backend.canvas.canvas_service import now
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions
from database.repositories.opora_verifications import Verifications

LOGGER = logging.getLogger(__name__)
CHECK_NAME = "formal/tlc"
EVIDENCE_KINDS = {"tlc": {"check": "formal/tlc", "status": "connected"},
                  "lean": {"check": "formal/lean", "status": "not_connected"}}
TOOL = {"name": "tlc", "version": "TLC2 2.19 (distribution 1.7.4), run by GitHub Actions",
        "distributionSha256": "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"}
# Mirrors INVARIANTS/PROPERTY of tools/formal/oporahub-execution/ExecutionAuthority.cfg (test-enforced).
CLAIMS = (("TypeOK", "invariant"), ("OneActiveOwner", "invariant"), ("NoUnauthorizedReceipt", "invariant"),
          ("OneReceiptPerExecution", "invariant"), ("Idempotency", "invariant"),
          ("MonotonicEpoch", "temporal-property"))
CONCLUSIONS = {"success": "passed", "failure": "failed", "cancelled": "cancelled"}
FAILURE_KINDS = {"positive_violation": "counterexample", "negative_not_detected": "failed",
                 "wrong_violation": "failed", "runner_error": "failed"}
TRUST = {"trust": "agent-reported", "independentlyVerified": False,
         "sourceBinding": "agent-reported", "currentEligibility": False}
ASSUMPTIONS = ["Observed GitHub check run of the PR's own workflow; not an independent verifier.",
               "Model inputs are the files under tools/formal at the reported commit; bytes are not imported.",
               "Finite abstract model; no refinement proof of the Python implementation."]


def request_id(check):
    return f"gh-check-{check['id']}"


def failures(annotations):
    """Case payloads the runner emitted as `::error title=formal/tlc <kind>::<json>` annotations."""
    result = []
    for note in annotations or []:
        title = str(note.get("title") or "")
        if not title.startswith(CHECK_NAME + " "):
            continue
        try:
            payload = json.loads(note.get("message") or "")
        except ValueError:
            continue
        if isinstance(payload, dict) and payload.get("kind") in FAILURE_KINDS:
            result.append({key: payload.get(key) for key in
                           ("model", "case", "config", "expect", "expectedInvariant", "kind", "violated")})
    return result[:32]


def outcome(check, cases):
    if check["conclusion"] == "success":
        return "passed"
    kinds = {case["kind"] for case in cases}
    if "positive_violation" in kinds:
        return "counterexample"
    if kinds:
        return "failed"
    return CONCLUSIONS.get(check["conclusion"], "inconclusive")


def _blob(path, role, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fingerprint = hashlib.sha256(data).hexdigest()
    return {"path": path, "role": role, "sha256": fingerprint, "bytes": len(data)}, {fingerprint: data}


def _linked(db, project, workspace, repository, number):
    repository = repository.casefold()
    return next((row for row in ExecutionPullRequests(db, project, workspace).listing()
                 if row["repository"] == repository and row["number"] == number), None)


def known(db, project, workspace, execution_id, check):
    return Verifications(db, project, workspace).replay(execution_id, request_id(check)) is not None


def record_check(db, project, workspace, check, *, repository, number, annotations=None, via):
    """Store one completed `formal/tlc` check run once; returns the record or None when not mappable."""
    if check.get("name") != CHECK_NAME or check.get("status") != "completed":
        return None
    link = _linked(db, project, workspace, repository, number)
    if link is None:
        return None
    store = Verifications(db, project, workspace)
    replay = store.replay(link["execution_id"], request_id(check))
    if replay:
        return replay[1]
    execution = Executions(db, project, workspace).read(link["execution_id"])
    cases = failures(annotations)
    result = outcome(check, cases)
    origin = {"kind": "github-check-run", "checkName": CHECK_NAME, "checkRunId": check["id"],
              "appId": check.get("appId"), "conclusion": check["conclusion"], "headSha": check["headSha"],
              "repository": repository.casefold(), "prNumber": number, "observedVia": via,
              "failureKinds": sorted({case["kind"] for case in cases})}
    claims = [{"id": name, "kind": kind, "statement": f"{name} as defined in tools/formal/oporahub-execution/"
               f"ExecutionAuthority.tla at commit {check['headSha']}."} for name, kind in CLAIMS]
    claims = [{**claim, "statementDigest": hashlib.sha256(claim["statement"].encode("utf-8")).hexdigest()}
              for claim in claims]
    metadata = {"tool": TOOL, "source": {"repository": repository.casefold(), "commitSha": check["headSha"]},
                "claims": claims, "assumptions": ASSUMPTIONS,
                "configuration": {"origin": "github-check-run", "checkName": CHECK_NAME,
                                  "mode": "exhaustive-model-checking", "cases": "tools/formal/*/cases.json",
                                  "negativeConfigsMustFail": True, "fairness": [], "axioms": []},
                "artifacts": []}
    artifacts, blobs = [], {}
    descriptor, data = _blob("check-run.json", "run-metadata", {**origin, "annotations": cases})
    artifacts.append(descriptor)
    blobs |= data
    if result == "counterexample":
        descriptor, data = _blob("counterexample.json", "counterexample",
                                 [case for case in cases if case["kind"] == "positive_violation"])
        artifacts.append(descriptor)
        blobs |= data
    fingerprint = validation.digest({key: execution[key] for key in
        ("project", "workspace", "nodeId", "executionId", "epoch", "acceptedRevision", "assignmentDigest")}
        | {"verification": metadata, "origin": origin})
    record = {"id": uuid.uuid4().hex, "project": project, "workspace": workspace, "nodeId": execution["nodeId"],
              "executionId": execution["executionId"], "epoch": execution["epoch"],
              "acceptedRevision": execution["acceptedRevision"], "assignmentDigest": execution["assignmentDigest"],
              "requestId": request_id(check), "requestDigest": fingerprint,
              "manifestDigest": validation.digest([]), "verification": metadata, "origin": origin,
              "createdAt": now(), **TRUST}
    summary = {"passed": "formal/tlc passed: every positive config exhausted, every negative config failed as expected.",
               "counterexample": "formal/tlc found a counterexample in a positive config.",
               "failed": "formal/tlc failed (vacuous negative, wrong violation or runner error)."}
    body = {"outcome": result, "checkedClaims": [name for name, _ in CLAIMS] if result == "passed" else [],
            "summary": summary.get(result, f"formal/tlc concluded {check['conclusion']}; not a pass."),
            "artifacts": sorted(artifacts, key=lambda item: item["path"])}
    report = {**body, "requestId": record["requestId"],
              "reportDigest": validation.digest({"verificationId": record["id"], "requestDigest": fingerprint,
                                                 "report": body}),
              "manifestDigest": validation.digest(body["artifacts"]), "createdAt": now(), **TRUST}
    store.store_blobs(blobs)
    store.insert(record)
    store.insert_report(record["id"], report)
    return {**record, "report": report}


def ingest_snapshot(db, project, workspace, snapshot):
    """GitHub evidence import hook: map observed `formal/tlc` checks; never fails the import."""
    if snapshot.get("complete") is not True:
        return []
    stored = []
    db.execute("SAVEPOINT formal_checks")
    try:
        for check in sorted(snapshot.get("checks", []), key=lambda item: item.get("id", 0)):
            link = _linked(db, project, workspace, snapshot["configuredRepository"], snapshot["prNumber"])
            if link is None or "id" not in check or known(db, project, workspace, link["execution_id"], check):
                continue
            value = record_check(db, project, workspace, check, repository=snapshot["configuredRepository"],
                                 number=snapshot["prNumber"], via="github-evidence")
            if value is not None:
                stored.append(value["id"])
    except (ValueError, KeyError, TypeError):
        db.execute("ROLLBACK TO formal_checks")
        LOGGER.warning("formal/tlc check mapping skipped for %s/%s.", project, workspace)
        stored = []
    db.execute("RELEASE formal_checks")
    return stored
