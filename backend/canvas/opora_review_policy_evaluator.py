"""Pure local policy evaluation, never merge permission or card completion."""
from backend.canvas.opora_review_policy_checks import required_checks
from backend.canvas.opora_review_policy_freshness import freshness, timestamp
from backend.canvas.opora_review_policy_ids import safe_id
from backend.canvas.opora_review_status import _reviews


def review_verdicts(snapshot, rules):
    reviews, invalid = _reviews(snapshot, snapshot["pr"]["headSha"])
    seen = {}
    for item in snapshot["reviews"]:
        if not isinstance(item, dict) or not safe_id(item.get("id")) or not safe_id(item.get("userId")):
            invalid = True
            continue
        identifier = item["id"]
        if identifier in seen and seen[identifier] != item:
            invalid = True
        seen[identifier] = item
    rejected = [item for item in reviews if item["state"] == "CHANGES_REQUESTED"]
    approved = [item for item in reviews if item["state"] == "APPROVED" and item["userId"] in rules["reviewerIds"]]
    marker = f"Opora-Plan: {snapshot['project']}/{snapshot['workspace']}@{snapshot['acceptedRevision']}"
    marked = [item for item in approved if isinstance(item.get("body"), str) and marker in item["body"].splitlines()]

    def verdict(items, minimum):
        chosen = rejected if rejected else items
        status = ("unknown" if invalid else "changes_requested" if rejected else
                  "approved" if len({item["userId"] for item in items}) >= minimum else "missing")
        return {"status": status, "minimum": minimum,
                "reviewIds": sorted(item["id"] for item in chosen),
                "reviewerIds": sorted({item["userId"] for item in chosen})}

    return verdict(approved, rules["minimumCodeApprovals"]), verdict(marked, rules["minimumPlanApprovals"]), invalid


def evaluate_policy(policy, snapshot, latest_attempt, current, now):
    """Inputs are validated server records; current contains scope, policy/head and config."""
    snapshot = snapshot or {}
    pr = snapshot.get("pr") or {}
    unknown = {"status": "unknown", "minimum": None, "reviewIds": [], "reviewerIds": []}
    result = {"evaluatorVersion": 1, "status": "unknown", "policyRevision": policy["id"] if policy else None,
              "evidenceId": snapshot.get("id"), "attemptSequence": latest_attempt.get("sequence") if latest_attempt else None,
              "binding": {"acceptedRevision": snapshot.get("acceptedRevision"),
                          "repositoryId": (snapshot.get("repository") or {}).get("id"), "prId": pr.get("id"),
                          "headRepoId": pr.get("headRepoId"), "headSha": pr.get("headSha"),
                          "baseSha": pr.get("baseSha"), "baseBranch": pr.get("baseRef")},
              "checks": {"policyVerified": False, "required": []},
              "codeReview": dict(unknown), "planReview": dict(unknown),
              "freshness": {"currentEligible": False, "observedFrom": snapshot.get("observedFrom"),
                            "observedUntil": snapshot.get("observedUntil"), "expiresAt": None,
                            "evaluatedAt": timestamp(now), "remoteFreshness": "historical-observation"}, "blockers": []}
    if policy is None or policy["enabled"] is not True:
        result["status"] = "not_configured" if policy is None else "disabled"
        result["blockers"] = ["review-policy-not-configured" if policy is None else "review-policy-disabled"]
        return result
    result["freshness"], result["blockers"] = freshness(policy, snapshot, latest_attempt, current, now)
    rules = policy["rules"]
    result["codeReview"]["minimum"] = rules["minimumCodeApprovals"]
    result["planReview"]["minimum"] = rules["minimumPlanApprovals"]
    if not result["freshness"]["currentEligible"]:
        result["checks"]["required"] = [{**item, "status": "unknown", "runId": None} for item in rules["requiredChecks"]]
        return result
    result["checks"], invalid_checks = required_checks(snapshot, rules["requiredChecks"], pr["headSha"])
    result["codeReview"], result["planReview"], invalid_reviews = review_verdicts(snapshot, rules)
    if invalid_checks:
        result["blockers"].append("invalid-check-evidence")
    if invalid_reviews:
        result["blockers"].append("invalid-review-evidence")
    result["checks"]["policyVerified"] = bool(rules["requiredChecks"]) and all(
        item["status"] == "passed" for item in result["checks"]["required"])
    if not result["checks"]["policyVerified"]:
        result["blockers"].append("required-checks-not-satisfied")
    for key in ("codeReview", "planReview"):
        if result[key]["status"] != "approved":
            result["blockers"].append("code-review-not-satisfied" if key == "codeReview" else "plan-review-not-satisfied")
    if pr.get("state") != "open" or pr.get("draft") is not False:
        result["blockers"].append("pr-not-open-ready")
    result["status"] = "unknown" if invalid_checks or invalid_reviews else "blocked" if result["blockers"] else "satisfied"
    return result
