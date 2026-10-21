"""Merge gate rules in the agent-state `review` stage (docs/oporahub-agent-state.md, docs/oporahub-review-jobs.md).

The stage keeps `review_gate_blocked` / `review_gate_pending` unless a gate rule names the exact
cause: then the stage reason is that gate reason (first by priority across open PR gates). Two
agent actions follow from the gates: `pr.update_branch` for a head behind its base branch and
`review.self_checks` when the self-check evidence for the current head is missing. Pure."""
from backend.canvas import opora_agent_state_rules as rules

BLOCKED_PRIORITY = ("open_security_findings", "self_checks_failed", "required_checks_failed")
PENDING_PRIORITY = ("stale_against_main", "self_checks_missing", "security_review_not_enqueued",
                    "security_review_in_progress", "required_checks_pending", "base_freshness_unobserved",
                    "template_unobserved", "template_incomplete")
VERBS = ("pr.update_branch", "review.self_checks")


def stage_reason(gates, status, fallback):
    """The most specific gate rule reason among open gates in `status`, else `fallback`."""
    present = {reason for item in gates if item["reviewGate"]["status"] == status
               for reason in item["reviewGate"]["reasons"]}
    order = BLOCKED_PRIORITY if status == "blocked" else PENDING_PRIORITY
    return next((reason for reason in order if reason in present), fallback)


def _action(verb, method, path, target, head, preconditions):
    return {"id": rules.stable_id("act_", verb, target, head), "verb": verb, "method": method, "path": path,
            "targetId": target, "preconditions": preconditions, "status": "ready"}


def actions(reviewing):
    result = []
    for item in (reviewing or {}).get("gates", []):
        reasons, readiness = item["reviewGate"]["reasons"], item.get("mergeReadiness") or {}
        base = readiness.get("base") or {}
        if "stale_against_main" in reasons and base:
            # agent-office PR upkeep rebases onto the base head; GitHub's update-branch is the equivalent API.
            result.append(_action("pr.update_branch", "PUT",
                                   f"github:/repos/{item['repository']}/pulls/{item['number']}/update-branch",
                                   item["executionId"], item["headSha"],
                                   {"repository": item["repository"], "number": item["number"],
                                    "expectedHeadSha": item["headSha"], "baseRef": base["baseRef"],
                                    "baseSha": base["baseSha"]}))
        if "self_checks_missing" in reasons:
            checks = readiness.get("selfChecks") or {}
            result.append(_action("review.self_checks", "POST", "/api/oporahub/review-jobs/self-checks",
                                  item["executionId"], item["headSha"],
                                  {"executionId": item["executionId"], "headSha": item["headSha"],
                                   "required": checks.get("missing", [])}))
    return result
