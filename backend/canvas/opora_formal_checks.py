"""Observed formal check runs -> execution-bound verification evidence.

Proofs and model checks run by machine (.github/workflows/formal.yml, formal-trusted.yml);
nobody reports them by hand. Whenever the server itself reads a completed `formal/tlc`,
`formal/lean` or `formal-trusted/*` check run (GitHub evidence import or the execution-PR
loop), this module maps conclusion + head SHA into the verification store, bound through
the execution -> PR link to execution and card. A PR without a linked execution has no
execution identity and is not recorded. What each kind claims: opora_formal_profiles.py.

Trust: `formal/*` stays `agent-reported` (the workflow is code of the PR under review).
`formal-trusted/*` becomes `ci-verified` only with verified provenance (base-branch
workflow run bound to this head, see github_formal_check_reader.provenance); otherwise it
is recorded as `agent-reported` with the failed provenance in `origin`. Contract:
docs/oporahub-verification.md. Callers own locks and the SQLite transaction.
"""
import hashlib
import json
import logging
import uuid

from backend.canvas import opora_formal_profiles as profiles
from backend.canvas import opora_verification_validation as validation
from backend.canvas.canvas_service import now
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions
from database.repositories.opora_verifications import Verifications

LOGGER = logging.getLogger(__name__)
CHECK_NAME = "formal/tlc"
# check name -> (evidence kind, from the trusted base-branch workflow)
CHECKS = {"formal/tlc": ("tlc", False), "formal/lean": ("lean", False),
          "formal-trusted/tlc": ("tlc", True), "formal-trusted/lean": ("lean", True)}
EVIDENCE_KINDS = {"tlc": {"check": "formal/tlc", "trustedCheck": "formal-trusted/tlc", "status": "connected"},
                  "lean": {"check": "formal/lean", "trustedCheck": "formal-trusted/lean", "status": "connected"}}
CLAIMS = tuple((identifier, kind) for identifier, kind, _, _ in profiles.CLAIMS)
TRUST = {"trust": "agent-reported", "independentlyVerified": False,
         "sourceBinding": "agent-reported", "currentEligibility": False}
# CI-verified = run by the base-branch workflow definition on this head; still not an independent
# verifier service, never eligible for automatic correctness decisions.
TRUST_CI = {"trust": "ci-verified", "independentlyVerified": False,
            "sourceBinding": "ci-verified", "currentEligibility": False}
OBSERVED = {False: "Observed GitHub check run of the PR's own workflow; not an independent verifier.",
            True: "Check run published by the base-branch workflow formal-trusted.yml; PR workflow changes "
                  "did not run. Not an independent verifier service."}
SUMMARY = {"passed": "{check} passed.", "counterexample": "{check} found a counterexample in a positive config.",
           "failed": "{check} failed: {kinds}.",
           "inconclusive": "{check} concluded {conclusion} without a clean, complete result; not a pass."}


def request_id(check):
    return f"gh-check-{check['id']}"


def failures(annotations, tool="tlc"):
    return profiles.failures(tool, annotations)


def outcome(check, cases, tool="tlc", audit=None):
    return profiles.outcome(tool, check, cases, audit)


def needs_annotations(check):
    """Lean always carries its axiom audit as an annotation; TLC only explains failures."""
    return CHECKS.get(check.get("name"), ("tlc",))[0] == "lean" or check.get("conclusion") != "success"


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


def _origin(check, tool, trusted, cases, provenance, repository, number, via):
    return {"kind": "github-check-run", "checkName": check["name"], "checkRunId": check["id"],
            "appId": check.get("appId"), "conclusion": check["conclusion"], "headSha": check["headSha"],
            "repository": repository.casefold(), "prNumber": number, "observedVia": via,
            "failureKinds": sorted({case["kind"] for case in cases}), "evidenceKind": tool,
            "trustedWorkflow": trusted, "provenance": provenance if trusted else None}


def record_check(db, project, workspace, check, *, repository, number, annotations=None, via, provenance=None):
    """Store one completed formal check run once; returns the record or None when not mappable."""
    if check.get("name") not in CHECKS or check.get("status") != "completed":
        return None
    link = _linked(db, project, workspace, repository, number)
    if link is None:
        return None
    store = Verifications(db, project, workspace)
    replay = store.replay(link["execution_id"], request_id(check))
    if replay:
        return replay[1]
    tool, trusted = CHECKS[check["name"]]
    verified = bool(trusted and provenance and provenance.get("verified") is True)
    execution = Executions(db, project, workspace).read(link["execution_id"])
    cases = profiles.failures(tool, annotations)
    audit = profiles.lean_audit(annotations) if tool == "lean" else None
    result = profiles.outcome(tool, check, cases, audit)
    origin = _origin(check, tool, trusted, cases, provenance, repository, number, via)
    tool_value, claims, assumptions, configuration = profiles.describe(tool, check, audit)
    metadata = {"tool": tool_value, "source": {"repository": repository.casefold(), "commitSha": check["headSha"]},
                "claims": claims, "assumptions": [OBSERVED[verified], *assumptions],
                "configuration": {"origin": "github-check-run", "checkName": check["name"], **configuration},
                "artifacts": []}
    artifacts, blobs = [], {}
    descriptor, data = _blob("check-run.json", "run-metadata", {**origin, "annotations": cases, "axiomAudit": audit})
    artifacts.append(descriptor)
    blobs |= data
    if result == "counterexample":
        descriptor, data = _blob("counterexample.json", "counterexample",
                                 [case for case in cases if case["kind"] == "positive_violation"])
        artifacts.append(descriptor)
        blobs |= data
    trust = TRUST_CI if verified else TRUST
    fingerprint = validation.digest({key: execution[key] for key in
        ("project", "workspace", "nodeId", "executionId", "epoch", "acceptedRevision", "assignmentDigest")}
        | {"verification": metadata, "origin": origin})
    record = {"id": uuid.uuid4().hex, "project": project, "workspace": workspace, "nodeId": execution["nodeId"],
              "executionId": execution["executionId"], "epoch": execution["epoch"],
              "acceptedRevision": execution["acceptedRevision"], "assignmentDigest": execution["assignmentDigest"],
              "requestId": request_id(check), "requestDigest": fingerprint,
              "manifestDigest": validation.digest([]), "verification": metadata, "origin": origin,
              "createdAt": now(), **trust}
    summary = SUMMARY.get(result, "{check} concluded {conclusion}; not a pass.").format(
        check=check["name"], conclusion=check["conclusion"],
        kinds=", ".join(origin["failureKinds"]) or check["conclusion"])
    body = {"outcome": result, "checkedClaims": [claim["id"] for claim in claims] if result == "passed" else [],
            "summary": summary, "artifacts": sorted(artifacts, key=lambda item: item["path"])}
    report = {**body, "requestId": record["requestId"],
              "reportDigest": validation.digest({"verificationId": record["id"], "requestDigest": fingerprint,
                                                 "report": body}),
              "manifestDigest": validation.digest(body["artifacts"]), "createdAt": now(), **trust}
    store.store_blobs(blobs)
    store.insert(record)
    store.insert_report(record["id"], report)
    return {**record, "report": report}


def ingest_snapshot(db, project, workspace, snapshot):
    """GitHub evidence import hook: map observed `formal/tlc` checks; never fails the import.

    Lean needs its audit annotation and trusted checks need provenance; both are read only by
    the execution-PR loop (opora_formal_check_poll.py), so this path leaves them alone."""
    if snapshot.get("complete") is not True:
        return []
    stored = []
    db.execute("SAVEPOINT formal_checks")
    try:
        for check in sorted(snapshot.get("checks", []), key=lambda item: item.get("id", 0)):
            if check.get("name") != CHECK_NAME:
                continue
            link = _linked(db, project, workspace, snapshot["configuredRepository"], snapshot["prNumber"])
            if link is None or "id" not in check or known(db, project, workspace, link["execution_id"], check):
                continue
            value = record_check(db, project, workspace, check, repository=snapshot["configuredRepository"],
                                 number=snapshot["prNumber"], via="github-evidence")
            if value is not None:
                stored.append(value["id"])
    except (ValueError, KeyError, TypeError):
        db.execute("ROLLBACK TO formal_checks")
        LOGGER.warning("formal check mapping skipped for %s/%s.", project, workspace)
        stored = []
    db.execute("RELEASE formal_checks")
    return stored
