"""Current policy authority is latest-attempt bound, time limited and fail closed."""
from datetime import UTC, datetime

from backend.canvas.opora_review_policy_ids import safe_id
from backend.canvas.opora_review_status import _sha, _time


def timestamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


def repository_name(value):
    return value.casefold() if isinstance(value, str) else None


def freshness(policy, snapshot, attempt, current, now):
    blockers = []
    start, end = _time(snapshot.get("observedFrom")), _time(snapshot.get("observedUntil"))
    age = policy["rules"]["maxObservationAgeSeconds"]
    expires = start + age if start is not None else None
    result = {"currentEligible": False, "observedFrom": snapshot.get("observedFrom"),
              "observedUntil": snapshot.get("observedUntil"), "expiresAt": timestamp(expires) if expires is not None else None,
              "evaluatedAt": timestamp(now), "remoteFreshness": "historical-observation"}
    if type(snapshot.get("schemaVersion")) is not int or snapshot.get("schemaVersion") != 2:
        blockers.append("refresh-required-for-policy")
    if not attempt or attempt.get("state") != "complete":
        blockers.append("latest-observation-not-complete")
    attempt = attempt or {}
    if (not safe_id(attempt.get("sequence")) or not safe_id(snapshot.get("attemptSequence"))
            or snapshot.get("attemptSequence") != attempt.get("sequence")
            or snapshot.get("id") != attempt.get("evidenceId")):
        blockers.append("not-latest-observation")
    for field in ("project", "workspace"):
        if any(item.get(field) != current.get(field) for item in (policy, snapshot, attempt)):
            blockers.append("scope-changed")
            break
    if (current.get("policyRevision") != policy["id"] or attempt.get("policyRevision") != policy["id"]):
        blockers.append("policy-changed-refresh-required")
    if (not current.get("acceptedRevision") or snapshot.get("acceptedRevision") != current.get("acceptedRevision")
            or attempt.get("acceptedRevision") != current.get("acceptedRevision")):
        blockers.append("accepted-revision-changed")
    repo, pr, config = snapshot.get("repository") or {}, snapshot.get("pr") or {}, current.get("repository") or {}
    pinned = policy["repository"]
    if (repo.get("id") != pinned["id"] or repository_name(repo.get("fullName")) != repository_name(pinned["fullName"])
            or repository_name(config.get("fullName")) != repository_name(pinned["fullName"])
            or config.get("baseBranch") != pinned["baseBranch"]
            or repository_name(snapshot.get("configuredRepository")) != repository_name(pinned["fullName"])
            or snapshot.get("configuredBaseBranch") != pinned["baseBranch"]
            or repository_name(attempt.get("configuredRepository")) != repository_name(pinned["fullName"])
            or attempt.get("configuredBranch") != pinned["baseBranch"] or pr.get("baseRef") != pinned["baseBranch"]):
        blockers.append("repository-configuration-or-identity-changed")
    if (not safe_id(pr.get("id")) or not safe_id(pr.get("headRepoId")) or not safe_id(pr.get("authorId"))
            or not safe_id(repo.get("id")) or not _sha(pr.get("headSha")) or not _sha(pr.get("baseSha"))
            or not safe_id(current.get("prNumber")) or not safe_id(pr.get("number")) or pr.get("number") != current.get("prNumber")
            or snapshot.get("prNumber") != current.get("prNumber") or attempt.get("prNumber") != current.get("prNumber")):
        blockers.append("invalid-pr-identity")
    if (snapshot.get("complete") is not True or
            any(not isinstance(snapshot.get(key), list) for key in ("checks", "statuses", "reviews"))):
        blockers.append("incomplete-or-invalid-observation")
    if (start is None or end is None or end < start or end > now or start > now
            or attempt.get("startedAt") != snapshot.get("observedFrom")
            or attempt.get("finishedAt") != snapshot.get("observedUntil")):
        blockers.append("invalid-observation-interval")
    elif now >= expires:
        blockers.append("observation-expired")
    result["currentEligible"] = not blockers
    return result, blockers
