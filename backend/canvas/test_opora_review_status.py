"""Evidence stays bound to exact revision, identities and Git SHA."""
from copy import deepcopy

import pytest

from backend.canvas.opora_review_status import evaluate

SHA, OLD, REV = "a" * 40, "b" * 40, "c" * 40
MARKER = f"Opora-Plan: project/workspace@{REV}"


def review(**updates):
    return {"id": 1, "userId": 2, "login": "reviewer", "userType": "User",
            "state": "APPROVED", "commitId": SHA, "submittedAt": "2026-10-20T12:00:00Z",
            "body": MARKER, "permission": "write", **updates}


def snapshot():
    return {"acceptedRevision": REV, "project": "project", "workspace": "workspace",
            "repository": {"id": 10, "fullName": "owner/repo"},
            "pr": {"id": 30, "number": 1, "authorId": 1, "headRepoId": 10,
                   "headSha": SHA, "body": MARKER}, "reviews": [review()],
            "checks": [{"id": 1, "appId": 8, "name": "tests", "headSha": SHA,
                        "status": "completed", "conclusion": "success"}],
            "statuses": [], "complete": True, "observedAt": "2026-10-20T12:30:00Z"}


def test_independent_reviews_and_observed_checks_never_grant_merge_authority():
    result = evaluate(snapshot(), REV, SHA)
    assert result["codeReview"]["status"] == result["planReview"]["status"] == "approved"
    assert result["checks"] == {"status": "passed", "observedCount": 1,
                                "policyVerified": False, "scope": "observed-only"}
    assert "verified" not in result and "mergeAllowed" not in result
    assert result["freshness"]["remoteFreshness"] == "historical-observation"
    assert result["freshness"]["status"] == "matches-observed-context"
    assert result["blockers"] == ["required-checks-and-trusted-provider-policy-not-configured"]


@pytest.mark.parametrize("update", [
    {"userId": 1}, {"userId": None}, {"userId": "2"}, {"userId": True},
    {"id": None}, {"permission": "unknown"}, {"permission": "read"},
    {"userType": "Bot"}, {"userType": None}, {"commitId": OLD},
    {"submittedAt": None}, {"submittedAt": "2026-10-20T12:00:00"},
])
def test_invalid_or_nonindependent_review_never_approves(update):
    data = snapshot()
    data["reviews"] = [review(**update)]
    assert evaluate(data, REV)["codeReview"]["status"] == "unknown"


@pytest.mark.parametrize("permission", ["admin", "maintain", "write", "push"])
def test_verified_write_permissions(permission):
    data = snapshot()
    data["reviews"] = [review(permission=permission)]
    assert evaluate(data, REV)["codeReview"]["status"] == "approved"


@pytest.mark.parametrize("body", ["", f"Example {MARKER}", f"> {MARKER}", MARKER + " extra", MARKER.replace(REV, OLD)])
def test_pr_marker_does_not_replace_exact_review_marker(body):
    data = snapshot()
    data["reviews"] = [review(body=body)]
    result = evaluate(data, REV)
    assert result["codeReview"]["status"] == "approved"
    assert result["planReview"]["status"] == "unknown"


def test_marker_can_be_standalone_line_in_multiline_review():
    data = snapshot()
    data["reviews"] = [review(body=f"Reviewed.\n{MARKER}\nLooks good.")]
    assert evaluate(data, REV)["planReview"]["status"] == "approved"


@pytest.mark.parametrize("state,expected", [("COMMENTED", "approved"), ("DISMISSED", "unknown"), ("CHANGES_REQUESTED", "changes_requested")])
def test_latest_decisive_review_supersedes_by_identity_not_login(state, expected):
    data = snapshot()
    data["reviews"].append(review(id=2, login="renamed", state=state, submittedAt="2026-10-20T13:00:00Z", body=""))
    assert evaluate(data, REV)["codeReview"]["status"] == expected


def test_old_sha_rejection_blocks_other_approval_until_same_reviewer_supersedes():
    data = snapshot()
    data["reviews"].append(review(id=2, userId=3, state="CHANGES_REQUESTED", commitId=OLD))
    assert evaluate(data, REV)["codeReview"]["status"] == "changes_requested"
    data["reviews"].append(review(id=3, userId=3, submittedAt="2026-10-20T14:00:00Z"))
    assert evaluate(data, REV)["codeReview"]["status"] == "approved"


@pytest.mark.parametrize("revision,head", [(OLD, SHA), (REV, OLD)])
def test_context_changes_invalidate_all_positive_verdicts(revision, head):
    result = evaluate(snapshot(), revision, head)
    assert result["freshness"]["status"] == "stale"
    assert all(result[key]["status"] == "unknown" for key in ("codeReview", "planReview", "checks"))


@pytest.mark.parametrize("data", [{}, {"complete": False}, {"complete": False, "acceptedRevision": REV}])
def test_incomplete_network_failure_is_safe(data):
    result = evaluate(data, REV)
    assert result["codeReview"]["status"] == result["planReview"]["status"] == result["checks"]["status"] == "unknown"


@pytest.mark.parametrize("collection", ["checks", "statuses", "reviews"])
def test_missing_collection_is_incomplete(collection):
    data = snapshot()
    del data[collection]
    assert evaluate(data, REV)["codeReview"]["status"] == "unknown"


def test_latest_check_run_and_status_context_override_older_attempts():
    data = snapshot()
    data["checks"].insert(0, {**data["checks"][0], "id": 0, "conclusion": "failure"})
    data["checks"][0]["id"] = 1
    data["checks"][1]["id"] = 2
    data["statuses"] = [{"id": 1, "context": "deploy", "sha": SHA, "state": "failure"},
                        {"id": 2, "context": "deploy", "sha": SHA, "state": "success"}]
    assert evaluate(data, REV)["checks"]["status"] == "passed"
    data["checks"].append({**data["checks"][0], "id": 3})
    assert evaluate(data, REV)["checks"]["status"] == "failed"


@pytest.mark.parametrize("conclusion,expected", [("neutral", "unknown"), ("skipped", "unknown"), ("failure", "failed"), ("timed_out", "failed"), (None, "unknown")])
def test_check_conclusions_are_conservative(conclusion, expected):
    data = snapshot()
    data["checks"][0]["conclusion"] = conclusion
    assert evaluate(data, REV)["checks"]["status"] == expected


def test_no_checks_or_other_sha_cannot_pass():
    data = snapshot()
    data["checks"][0]["headSha"] = OLD
    assert evaluate(data, REV)["checks"]["status"] == "unknown"
    data["checks"] = []
    assert evaluate(data, REV)["checks"]["status"] == "unknown"


def test_pending_and_malformed_checks():
    data = snapshot()
    data["checks"][0]["status"] = "in_progress"
    assert evaluate(data, REV)["checks"]["status"] == "pending"
    data["checks"][0]["appId"] = None
    assert evaluate(data, REV)["checks"]["status"] == "unknown"


def test_evaluation_does_not_mutate_snapshot():
    data = snapshot()
    before = deepcopy(data)
    evaluate(data, REV)
    assert data == before

@pytest.mark.parametrize("field,value", [("authorId", None), ("authorId", True), ("id", "30"), ("headRepoId", None), ("headSha", "not-a-sha")])
def test_missing_or_malformed_pr_identity_is_unknown(field, value):
    data = snapshot()
    data["pr"][field] = value
    assert evaluate(data, REV)["codeReview"]["status"] == "unknown"


def test_old_sha_dismissal_does_not_resurrect_earlier_approval():
    data = snapshot()
    data["reviews"].append(review(id=2, state="DISMISSED", commitId=OLD, submittedAt="2026-10-20T13:00:00Z"))
    assert evaluate(data, REV)["codeReview"]["status"] == "unknown"


def test_conflicting_duplicate_review_and_check_ids_fail_closed():
    data = snapshot()
    data["reviews"].append(review(state="DISMISSED"))
    assert evaluate(data, REV)["codeReview"]["status"] == "unknown"
    data = snapshot()
    data["checks"].append({**data["checks"][0], "conclusion": "failure"})
    assert evaluate(data, REV)["checks"]["status"] == "unknown"


@pytest.mark.parametrize("permission", ["unknown", None, "unrecognized"])
def test_unknown_permission_cannot_hide_another_reviewers_rejection(permission):
    data = snapshot()
    data["reviews"].append(review(id=2, userId=3, state="CHANGES_REQUESTED", permission=permission))
    result = evaluate(data, REV)
    assert result["codeReview"]["status"] == result["planReview"]["status"] == "unknown"
    assert "invalid-review-evidence" in result["blockers"]


@pytest.mark.parametrize("permission", ["read", "none", "triage"])
def test_known_nonwrite_permission_does_not_block_eligible_review(permission):
    data = snapshot()
    data["reviews"].append(review(id=2, userId=3, state="CHANGES_REQUESTED", permission=permission))
    assert evaluate(data, REV)["codeReview"]["status"] == "approved"


@pytest.mark.parametrize("observed_at", [None, "", "invalid", "2026-10-20T12:30:00"])
def test_missing_or_invalid_observation_timestamp_is_unknown(observed_at):
    data = snapshot()
    data["observedAt"] = observed_at
    result = evaluate(data, REV)
    assert result["freshness"]["status"] == "unknown"
    assert all(result[key]["status"] == "unknown" for key in ("codeReview", "planReview", "checks"))
