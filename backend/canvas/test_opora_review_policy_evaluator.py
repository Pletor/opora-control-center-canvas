"""Local policy passes only fresh, newest, provider-bound server evidence."""
from copy import deepcopy
from datetime import datetime

import pytest

from backend.canvas.opora_review_policy_evaluator import evaluate_policy
from backend.canvas.test_opora_review_status import REV, SHA, review, snapshot

POLICY = "d" * 40
EVIDENCE = "e" * 40
START = "2026-10-20T12:29:50+00:00"
END = "2026-10-20T12:30:00+00:00"
NOW = datetime.fromisoformat(END).timestamp()


@pytest.fixture
def inputs():
    policy = {"id": POLICY, "enabled": True, "project": "project", "workspace": "workspace",
              "repository": {"id": 10, "fullName": "owner/repo", "baseBranch": "main"},
              "rules": {"requiredChecks": [{"appId": 8, "name": "tests"}], "reviewerIds": [2],
                        "minimumCodeApprovals": 1, "minimumPlanApprovals": 1, "maxObservationAgeSeconds": 60}}
    data = snapshot() | {"schemaVersion": 2, "id": EVIDENCE, "attemptSequence": 1,
                         "observedFrom": START, "observedUntil": END, "prNumber": 1,
                         "configuredRepository": "owner/repo", "configuredBaseBranch": "main"}
    data["pr"].update(baseRef="main", baseSha="f" * 40, state="open", draft=False)
    attempt = {"project": "project", "workspace": "workspace", "sequence": 1, "prNumber": 1,
               "configuredRepository": "owner/repo", "configuredBranch": "main", "acceptedRevision": REV,
               "policyRevision": POLICY, "startedAt": START, "finishedAt": END,
               "state": "complete", "evidenceId": EVIDENCE}
    current = {"project": "project", "workspace": "workspace", "prNumber": 1,
               "acceptedRevision": REV, "policyRevision": POLICY,
               "repository": {"fullName": "owner/repo", "baseBranch": "main"}}
    return policy, data, attempt, current


def evaluate(inputs, now=NOW):
    return evaluate_policy(*inputs, now)


def test_pass_is_revision_sha_policy_bound_and_does_not_mutate_inputs(inputs):
    before = deepcopy(inputs)
    result = evaluate(inputs)
    assert result["status"] == "satisfied" and result["checks"]["policyVerified"]
    assert result["binding"]["headSha"] == SHA and result["binding"]["acceptedRevision"] == REV
    assert result["policyRevision"] == POLICY and result["evidenceId"] == EVIDENCE
    assert result["blockers"] == [] and result["freshness"]["currentEligible"]
    assert inputs == before
    assert "mergeAllowed" not in result and "done" not in result


@pytest.mark.parametrize("state", ["pending", "failed", "context_changed"])
def test_newer_attempt_never_falls_back_to_old_success(inputs, state):
    inputs[2].update(sequence=2, state=state, evidenceId=None)
    result = evaluate(inputs)
    assert result["status"] == "unknown" and not result["checks"]["policyVerified"]
    assert "latest-observation-not-complete" in result["blockers"]


@pytest.mark.parametrize("index,key,value", [
    (1, "schemaVersion", 1), (1, "attemptSequence", 0), (1, "id", "0" * 40),
    (2, "policyRevision", None), (3, "policyRevision", "0" * 40),
    (3, "acceptedRevision", "0" * 40), (2, "acceptedRevision", "0" * 40),
    (1, "workspace", "foreign"), (2, "prNumber", 2), (1, "complete", False),
    (1, "observedUntil", "2026-10-20T12:31:00+00:00"), (1, "observedFrom", "bad"),
])
def test_changed_or_untrusted_context_is_unknown(inputs, index, key, value):
    inputs[index][key] = value
    result = evaluate(inputs)
    assert result["status"] == "unknown" and not result["checks"]["policyVerified"]


def test_ttl_counts_from_start_and_expires_at_boundary(inputs):
    assert evaluate(inputs, NOW + 49)["status"] == "satisfied"
    assert "observation-expired" in evaluate(inputs, NOW + 50)["blockers"]


@pytest.mark.parametrize("field,value", [("id", 11), ("fullName", "another/repo")])
def test_repository_recreation_or_configuration_change(inputs, field, value):
    inputs[1]["repository"][field] = value
    assert evaluate(inputs)["status"] == "unknown"


def test_reader_repository_case_is_normalized_but_branch_is_exact(inputs):
    inputs[1]["repository"]["fullName"] = "Owner/Repo"
    assert evaluate(inputs)["status"] == "satisfied"
    inputs[1]["pr"]["baseRef"] = "Main"
    assert evaluate(inputs)["status"] == "unknown"


@pytest.mark.parametrize("update,status", [({"appId": 9}, "missing"), ({"headSha": "0" * 40}, "missing"),
    ({"status": "in_progress", "conclusion": None}, "pending"), ({"conclusion": "neutral"}, "unknown"),
    ({"conclusion": "skipped"}, "unknown"), ({"conclusion": "failure"}, "failed")])
def test_required_check_exact_provider_sha_and_result(inputs, update, status):
    inputs[1]["checks"][0].update(update)
    result = evaluate(inputs)
    assert not result["checks"]["policyVerified"]
    assert result["checks"]["required"][0]["status"] == status


def test_newer_pending_rerun_supersedes_pass_and_status_cannot_replace_it(inputs):
    inputs[1]["checks"].append({**inputs[1]["checks"][0], "id": 2, "status": "queued", "conclusion": None})
    inputs[1]["statuses"] = [{"id": 99, "context": "tests", "state": "success", "sha": SHA}]
    assert evaluate(inputs)["checks"]["required"][0]["status"] == "pending"


def test_duplicate_check_id_conflicts_even_under_different_app(inputs):
    inputs[1]["checks"].append({**inputs[1]["checks"][0], "appId": 9})
    assert "invalid-check-evidence" in evaluate(inputs)["blockers"]


def test_unrequired_failure_is_visible_but_not_an_implicit_requirement(inputs):
    inputs[1]["checks"].append({**inputs[1]["checks"][0], "id": 2, "name": "optional", "conclusion": "failure"})
    assert evaluate(inputs)["status"] == "satisfied"


@pytest.mark.parametrize("changes", [{"userId": 1}, {"userId": 3}, {"userType": "Bot"},
    {"permission": "unknown"}, {"permission": "read"}, {"commitId": "0" * 40}, {"body": "not exact marker"}])
def test_review_identity_permissions_and_marker(inputs, changes):
    inputs[1]["reviews"][0].update(changes)
    assert evaluate(inputs)["status"] != "satisfied"


def test_unknown_permission_cannot_erase_outside_allowlist_blocker(inputs):
    inputs[1]["reviews"].append(review(id=2, userId=3, state="CHANGES_REQUESTED", permission="unknown"))
    assert evaluate(inputs)["status"] == "unknown"
    inputs[1]["reviews"][1]["permission"] = "write"
    assert evaluate(inputs)["codeReview"]["status"] == "changes_requested"


def test_dismissal_and_comment_decisions(inputs):
    inputs[1]["reviews"].append(review(id=2, state="COMMENTED", submittedAt=END))
    assert evaluate(inputs)["status"] == "satisfied"
    inputs[1]["reviews"][1]["state"] = "DISMISSED"
    assert evaluate(inputs)["codeReview"]["status"] == "missing"


def test_distinct_accounts_count_once(inputs):
    inputs[0]["rules"].update(reviewerIds=[2, 3], minimumCodeApprovals=2)
    inputs[1]["reviews"].append(review(id=2, submittedAt=END))
    assert evaluate(inputs)["codeReview"]["status"] == "missing"
    inputs[1]["reviews"].append(review(id=3, userId=3))
    assert evaluate(inputs)["status"] == "satisfied"


def test_conflicting_review_identity_cannot_count_as_two_accounts(inputs):
    inputs[1]["reviews"].append(review(userId=3))
    assert evaluate(inputs)["status"] == "unknown"


def test_no_policy_and_disabled_are_never_vacuous_success(inputs):
    assert evaluate_policy(None, inputs[1], inputs[2], inputs[3], NOW)["status"] == "not_configured"
    inputs[0]["enabled"] = False
    assert evaluate(inputs)["status"] == "disabled"
