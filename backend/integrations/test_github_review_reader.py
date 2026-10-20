"""Network-free fixtures prove exact identity, bounded pagination, and failed observations."""
import copy

import pytest

from backend.integrations import github_review_reader as module
from backend.integrations.github_review_reader import GitHubReviewReader
from backend.integrations.github_review_transport import GitHubReadError

SHA = "a" * 40
ROOT = "/repos/example/project"
PR = ROOT + "/pulls/7"
REPO = {"id": 1, "full_name": "example/project"}
PULL = {"id": 2, "number": 7, "user": {"id": 3}, "draft": False, "state": "open", "body": "Plan",
        "base": {"repo": REPO, "ref": "main", "sha": "b" * 40},
        "head": {"repo": {"id": 4}, "sha": SHA}}
REVIEW = {"id": 5, "user": {"id": 6, "login": "reviewer", "type": "User"},
          "state": "APPROVED", "commit_id": SHA, "submitted_at": "2026-10-20T12:00:00Z", "body": "Opora-Plan: p/w@revision"}
CHECK = {"id": 8, "app": {"id": 9}, "name": "tests", "head_sha": SHA, "status": "completed", "conclusion": "success"}
STATUS = {"id": 10, "context": "ci", "state": "success"}


class Fixture:
    def __init__(self):
        self.calls = []
        self.responses = {
            ROOT: REPO, PR: PULL,
            PR + "/reviews?per_page=100&page=1": [REVIEW],
            ROOT + "/collaborators/reviewer/permission": {"permission": "write", "user": REVIEW["user"]},
            ROOT + f"/commits/{SHA}/check-runs?filter=all&per_page=100&page=1": {"total_count": 1, "check_runs": [CHECK]},
            ROOT + f"/commits/{SHA}/statuses?per_page=100&page=1": [STATUS],
        }

    def __call__(self, path, *, timeout):
        assert 0 < timeout <= 60
        self.calls.append(path)
        result = self.responses[path]
        if callable(result):
            result = result()
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result) if isinstance(result, tuple) else (copy.deepcopy(result), {})


def read(fake):
    return GitHubReviewReader(transport=fake).read("example/project", 7)


def test_normalized_server_observation_has_only_required_fields():
    fake = Fixture()
    observed = read(fake)
    assert observed["repository"] == {"id": 1, "fullName": "example/project"}
    assert observed["pr"]["headRepoId"] == 4  # Fork PR remains bound to configured base repository.
    assert observed["reviews"][0]["permission"] == "write"
    assert observed["reviews"][0]["body"] == REVIEW["body"]
    assert observed["checks"] == [{"id": 8, "appId": 9, "name": "tests", "headSha": SHA, "status": "completed", "conclusion": "success"}]
    assert observed["statuses"] == [{"id": 10, "context": "ci", "sha": SHA, "state": "success"}]
    assert observed["complete"] and observed["observedAt"]
    assert fake.calls.count(PR) == 2


@pytest.mark.parametrize("repository,number", [("https://evil.test/x", 7), ("a/b/../c", 7), ("a/b?x=y", 7),
                                               ("a/b", True), ("a/b", 0), ("a/b", "7")])
def test_invalid_input_never_reaches_transport(repository, number):
    fake = Fixture()
    with pytest.raises(GitHubReadError):
        GitHubReviewReader(transport=fake).read(repository, number)
    assert not fake.calls


@pytest.mark.parametrize("change", ["repo", "sha", "body", "base", "draft"])
def test_changed_pr_during_collection_fails_closed(change):
    fake, after = Fixture(), copy.deepcopy(PULL)
    if change == "repo":
        after["base"]["repo"]["id"] = 90
    elif change == "sha":
        after["head"]["sha"] = "c" * 40
    elif change == "body":
        after["body"] = "Different plan"
    elif change == "base":
        after["base"]["ref"] = "other"
    else:
        after["draft"] = True
    values = iter([PULL, after])
    fake.responses[PR] = lambda: next(values)
    with pytest.raises(GitHubReadError):
        read(fake)


@pytest.mark.parametrize("code", [403, 404])
def test_permission_unavailable_is_unknown_but_core_collection_unavailable_fails(code):
    fake = Fixture()
    fake.responses[ROOT + "/collaborators/reviewer/permission"] = GitHubReadError(status=code)
    assert read(fake)["reviews"][0]["permission"] == "unknown"
    fake.responses[PR + "/reviews?per_page=100&page=1"] = GitHubReadError(status=code)
    with pytest.raises(GitHubReadError):
        read(fake)


def test_wrong_reviewer_identity_and_check_sha_are_rejected():
    fake = Fixture()
    fake.responses[ROOT + "/collaborators/reviewer/permission"] = {"permission": "admin", "user": {"id": 999, "login": "reviewer"}}
    with pytest.raises(GitHubReadError):
        read(fake)
    fake = Fixture()
    fake.responses[ROOT + f"/commits/{SHA}/check-runs?filter=all&per_page=100&page=1"] = {
        "total_count": 1, "check_runs": [{**CHECK, "head_sha": "c" * 40}]}
    with pytest.raises(GitHubReadError):
        read(fake)


def test_own_pagination_ignores_untrusted_next_url_and_keeps_later_dismissal():
    fake = Fixture()
    fake.responses[PR + "/reviews?per_page=100&page=1"] = ([REVIEW], {"link": '<https://evil.test/steal>; rel="next"'})
    fake.responses[PR + "/reviews?per_page=100&page=2"] = [{**REVIEW, "id": 12, "state": "DISMISSED"}]
    observed = read(fake)
    assert [item["state"] for item in observed["reviews"]] == ["APPROVED", "DISMISSED"]
    assert all(path.startswith(ROOT) for path in fake.calls)


def test_pagination_overflow_duplicates_and_total_count_mismatch_fail(monkeypatch):
    monkeypatch.setattr(module, "MAX_PAGES", 1)
    fake = Fixture()
    fake.responses[PR + "/reviews?per_page=100&page=1"] = ([REVIEW], {"link": '<ignored>; rel="next"'})
    with pytest.raises(GitHubReadError, match="pagination"):
        read(fake)
    fake.responses[PR + "/reviews?per_page=100&page=1"] = [REVIEW, REVIEW]
    with pytest.raises(GitHubReadError):
        read(fake)
    fake = Fixture()
    fake.responses[ROOT + f"/commits/{SHA}/check-runs?filter=all&per_page=100&page=1"] = {"total_count": 2, "check_runs": [CHECK]}
    with pytest.raises(GitHubReadError):
        read(fake)


def test_budget_prevents_unbounded_permission_requests(monkeypatch):
    fake = Fixture()
    monkeypatch.setattr(module, "MAX_REQUESTS", 3)
    with pytest.raises(GitHubReadError, match="limit"):
        read(fake)
    assert len(fake.calls) == 3


@pytest.mark.parametrize("value", [None, {}, {"total_count": 0, "check_runs": []}, [{"id": True}], [{**REVIEW, "commit_id": "abc1234"}]])
def test_malformed_reviews_fail_closed(value):
    fake = Fixture()
    fake.responses[PR + "/reviews?per_page=100&page=1"] = value
    with pytest.raises(GitHubReadError):
        read(fake)


def test_full_page_without_link_still_requires_next_page():
    fake = Fixture()
    fake.responses[PR + "/reviews?per_page=100&page=1"] = [{**REVIEW, "id": 100 + n} for n in range(100)]
    fake.responses[PR + "/reviews?per_page=100&page=2"] = []
    assert len(read(fake)["reviews"]) == 100
    assert PR + "/reviews?per_page=100&page=2" in fake.calls
    assert fake.calls.count(ROOT + "/collaborators/reviewer/permission") == 1


def test_expired_collection_never_calls_transport(monkeypatch):
    fake = Fixture()
    times = iter([0, 61])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))
    with pytest.raises(GitHubReadError, match="limit"):
        read(fake)
    assert not fake.calls


def test_permission_network_failure_is_not_silently_ignored():
    fake = Fixture()
    fake.responses[ROOT + "/collaborators/reviewer/permission"] = GitHubReadError(status=500)
    with pytest.raises(GitHubReadError):
        read(fake)


@pytest.mark.parametrize("field,value", [("body", False), ("submitted_at", "invalid-date"), ("state", "UNKNOWN")])
def test_malformed_review_fields_are_not_coerced(field, value):
    fake = Fixture()
    fake.responses[PR + "/reviews?per_page=100&page=1"] = [{**REVIEW, field: value}]
    with pytest.raises(GitHubReadError):
        read(fake)
