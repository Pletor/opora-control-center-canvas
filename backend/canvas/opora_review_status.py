"""Pure, conservative interpretation of immutable GitHub observations.

These verdicts describe observed evidence, never branch protection or merge permission.
"""
import re
from datetime import datetime

from backend.canvas.opora_review_checks import observed_checks

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_PERMISSIONS = {"admin", "maintain", "write", "push"}
_DECISIVE = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


def _id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sha(value):
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def _time(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.timestamp() if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def _reviews(snapshot, sha):
    """Comments preserve decisions; dismissal supersedes an approval, even on older SHA."""
    author = snapshot.get("pr", {}).get("authorId")
    if not _id(author):
        return [], True
    latest, invalid = {}, False
    for review in snapshot.get("reviews", []):
        if not isinstance(review, dict):
            invalid = True
            continue
        state = review.get("state")
        if state not in _DECISIVE:
            if state not in {"COMMENTED", "PENDING"}:
                invalid = True
            continue
        user, identifier, submitted = review.get("userId"), review.get("id"), _time(review.get("submittedAt"))
        if not _id(user) or not _id(identifier) or submitted is None:
            invalid = True
            continue
        # A malformed later decision cannot leave an older approval effective.
        rank = (submitted, identifier)
        previous = latest.get(user)
        if previous is None or rank > previous[0]:
            latest[user] = (rank, review)
        elif rank == previous[0] and review != previous[1]:
            invalid = True
    eligible = []
    for _, review in latest.values():
        if review["userId"] == author or review.get("userType") != "User":
            continue
        permission = review.get("permission")
        if permission not in _PERMISSIONS:
            # Failed permission lookup must not silently discard a blocking review.
            if permission not in {"read", "none", "triage"}:
                invalid = True
            continue
        if not _sha(review.get("commitId")):
            invalid = True
            continue
        if review["state"] == "CHANGES_REQUESTED" or review["commitId"] == sha:
            eligible.append(review)
    return eligible, invalid


def evaluate(snapshot, current_revision, current_head_sha=None):
    """Evaluate a normalized snapshot without I/O or any authority to merge."""
    blockers = []
    pr = snapshot.get("pr") or {}
    sha = pr.get("headSha")
    valid = (snapshot.get("complete") is True and _sha(sha)
             and _time(snapshot.get("observedAt")) is not None
             and _id(pr.get("id")) and _id(pr.get("number"))
             and _id(pr.get("authorId")) and _id(pr.get("headRepoId"))
             and _id((snapshot.get("repository") or {}).get("id"))
             and isinstance(snapshot.get("acceptedRevision"), str)
             and bool(snapshot.get("acceptedRevision"))
             and all(isinstance(snapshot.get(key), str) and snapshot[key] for key in ("project", "workspace"))
             and all(isinstance(snapshot.get(key), list) for key in ("reviews", "checks", "statuses")))
    stale = (snapshot.get("acceptedRevision") != current_revision
             or (current_head_sha is not None and sha != current_head_sha))
    freshness = "stale" if stale else "matches-observed-context" if valid else "unknown"
    if stale:
        blockers.append("stale-revision-or-head")
    if not valid:
        blockers.append("incomplete-or-invalid-observation")
    reviews, invalid_reviews = _reviews(snapshot, sha) if valid else ([], True)
    if invalid_reviews:
        blockers.append("invalid-review-evidence")
    rejected = [r["id"] for r in reviews if r["state"] == "CHANGES_REQUESTED"]
    approved = [r for r in reviews if r["state"] == "APPROVED" and r["commitId"] == sha]
    marker = f"Opora-Plan: {snapshot.get('project')}/{snapshot.get('workspace')}@{snapshot.get('acceptedRevision')}"
    marked = [r for r in approved if isinstance(r.get("body"), str) and marker in r["body"].splitlines()]

    def verdict(items):
        if stale or not valid or invalid_reviews:
            return {"status": "unknown", "reviewIds": []}
        if rejected:
            return {"status": "changes_requested", "reviewIds": sorted(rejected)}
        return {"status": "approved" if items else "unknown", "reviewIds": sorted(r["id"] for r in items)}

    code, plan = verdict(approved), verdict(marked)
    if code["status"] != "approved":
        blockers.append("independent-code-review-missing-or-blocked")
    if plan["status"] != "approved":
        blockers.append("revision-bound-plan-review-missing-or-blocked")
    checks = observed_checks(snapshot, sha) if valid else {"status": "unknown"}
    if stale:
        checks["status"] = "unknown"
    checks.update(policyVerified=False, scope="observed-only")
    blockers.append("required-checks-and-trusted-provider-policy-not-configured")
    return {"codeReview": code, "planReview": plan, "checks": checks,
            "freshness": {"status": freshness, "observedAt": snapshot.get("observedAt"), "remoteFreshness": "historical-observation"},
            "blockers": blockers}

