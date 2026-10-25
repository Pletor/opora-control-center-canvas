"""Server-owned fixture evidence in the existing verification store, never worker-imported truth."""
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.opora_verification_validation import digest

KIND = "harness-server-verifier"
BINDING = ("executionId", "epoch", "project", "workspace", "nodeId", "acceptedRevision", "assignmentDigest")
PENDING = {"trust": "server-pending", "independentlyVerified": False,
           "sourceBinding": "canvas-verified", "currentEligibility": False}


def request(record, pinned, image):
    binding = {key: record[key] for key in BINDING}
    identity = {"execution": binding, "plan": pinned["resource"], "baseline": pinned["baseline"],
                "candidate": pinned["candidate"], "problem": pinned["plan"]["problem"],
                "image": image, "protocol": "harness.server-fixtures/1"}
    metadata = {"tool": {"name": "node-fixtures", "version": "harness.server-fixtures/1", "distributionSha256": image.split(":")[-1]},
                "source": {"repository": None, "commitSha": None},
                "claims": [{"id": "fixture-output", "kind": "fixture", "statement": "Exact outputs on the accepted predeclared cases."}],
                "assumptions": ["Configured native process and pinned container image are trusted.",
                                "Fixture coverage is not a proof of production correctness."],
                "configuration": {"image": image, "network": "none", "readOnly": True, "nonroot": True}, "artifacts": []}
    return {"id": uuid.uuid4().hex, "domain": "harness-fixtures", **binding, "requestId": "harness-verifier-" + str(record["epoch"]),
            "requestDigest": digest(identity), "manifestDigest": digest([]), "verification": metadata,
            "createdAt": now(), "origin": {"kind": KIND, **identity}, "plannedTrials": 2 * len(pinned["plan"]["cases"]),
            **PENDING}


def report(record, observed, current):
    complete = observed["complete"] and observed["cleanupComplete"] and current
    passed = complete and all(t["outcome"] == "pass" for t in observed["trials"] if t["side"] == "candidate")
    outcome = "passed" if passed else "failed" if complete else "inconclusive"
    body = {"outcome": outcome, "checkedClaims": ["fixture-output"] if passed else [],
            "summary": "Server-owned paired fixture rerun; no production or promotion claim.", "artifacts": [],
            "paired": observed, "authorityCurrentAtCompletion": current, "promotionAllowed": False}
    return {**body, "requestId": record["requestId"], "reportDigest": digest({"request": record["requestDigest"], "report": body}),
            "manifestDigest": digest([]), "createdAt": now(), "trust": "server-observed",
            "independentlyVerified": complete, "sourceBinding": "canvas-verified", "currentEligibility": False}


def interrupted(planned, cleanup):
    return {"trials": [], "plannedTrials": planned, "observedTrials": 0, "improvements": 0,
            "regressions": 0, "unknownPairs": planned // 2, "complete": False, "cleanupComplete": cleanup,
            "reason": "interrupted-server-run", "observedCoverage": "unknown-before-recovery"}
