"""Join current policy with newest durable attempt, independently of legacy verdicts."""
import time

from backend.canvas.opora_review_policy_evaluator import evaluate_policy
from database.repositories.opora_review_attempts import Attempts
from database.repositories.opora_review_evidence import ReviewEvidenceRepository
from database.repositories.opora_review_policy import Policies


def policy_evaluation(service, pid, wid, pr_number, current_context, snapshot=None, cache=None):
    """Caller holds graph/project locks; no network or mutation occurs here."""
    db = service.db_for(pid)
    cache = {} if cache is None else cache
    policy_key = ("review-policy", pid, wid)
    if policy_key not in cache:
        policies = Policies(db, pid, wid)
        head = policies.head()
        cache[policy_key] = (head, policies.read(head) if head else None)
    head, policy = cache[policy_key]
    config = current_context.get("config")
    attempt_key = ("review-attempt", pid, wid, pr_number,
                   config["repository"] if config else None, config["branch"] if config else None)
    if attempt_key not in cache:
        cache[attempt_key] = Attempts(db, pid, wid).latest(pr_number, config) if config else None
    latest = cache[attempt_key]
    if snapshot is None and latest and latest["evidenceId"]:
        snapshot = ReviewEvidenceRepository(db, pid, wid).read(latest["evidenceId"])
    current = {"project": pid, "workspace": wid, "prNumber": pr_number,
               "acceptedRevision": current_context.get("acceptedHead"), "policyRevision": head,
               "repository": {"fullName": config["repository"], "baseBranch": config["branch"]} if config else None}
    if "policy-evaluated-at" not in cache:
        cache["policy-evaluated-at"] = time.time()
    result = evaluate_policy(policy, snapshot, latest, current, cache["policy-evaluated-at"])
    if not current_context.get("available") and result["status"] not in ("not_configured", "disabled"):
        result["status"] = "unknown"
        result["checks"]["policyVerified"] = False
        result["freshness"]["currentEligible"] = False
        result["blockers"].append("evidence-context-unavailable")
    return result
