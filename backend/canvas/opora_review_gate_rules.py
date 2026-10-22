"""Additional merge gate rules on top of the code review gate (docs/oporahub-review-jobs.md, "Pravidla brány").

security review, pre-PR self-check evidence, merge-queue freshness against the current base head
and the PR template. Each rule is off when its config section is missing. Read-only."""
from backend.canvas import opora_review_merge_queue as merge_queue
from backend.canvas import opora_review_security as security
from backend.canvas import opora_review_self_checks as self_checks
from database.repositories.opora_review_gate_facts import ReviewGateFacts

BLOCKING = ("open_security_findings", "self_checks_failed", "required_checks_failed")


def evaluate(store, link, evidence, config, now=None):
    """(reasons, details) for one linked PR head; `details` is the gate item's `mergeReadiness`."""
    reasons, details = [], {}
    found, details["security"] = security.evaluate(store, link, config)
    reasons += found
    checks = self_checks.status(store.db, *store.scope, link, config)
    details["selfChecks"] = checks
    if checks["status"] == "failed":
        reasons.append("self_checks_failed")
    elif checks["status"] == "missing":
        reasons.append("self_checks_missing")
    found, queue = merge_queue.evaluate(ReviewGateFacts(store.db, *store.scope), link, evidence, config, now)
    return reasons + found, {**details, **queue}
