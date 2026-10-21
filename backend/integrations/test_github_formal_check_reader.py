"""Formal check reader builds fixed GET paths and validates GitHub JSON offline."""
import pytest

from backend.integrations.github_formal_check_reader import GitHubFormalCheckReader
from backend.integrations.github_review_transport import GitHubReadError

SHA = "a" * 40


def run(conclusion="failure", name="formal/tlc", sha=SHA):
    return {"id": 5, "app": {"id": 15368}, "name": name, "head_sha": sha, "status": "completed",
            "conclusion": conclusion}


class Transport:
    def __init__(self, responses):
        self.paths, self.responses = [], list(responses)

    def __call__(self, path, *, timeout):
        self.paths.append(path)
        return self.responses.pop(0), {}


def test_checks_and_annotations_use_fixed_paths():
    transport = Transport([{"total_count": 3, "check_runs": [run(), run(name="formal/tlc-other"),
                                                             {**run(name="formal/lean"), "id": 6, "external_id": "77"}]},
                           [{"title": "formal/tlc positive_violation", "message": "{}"}]])
    reader = GitHubFormalCheckReader(transport)
    assert reader.checks("owner/repo", SHA) == [
        {"id": 5, "appId": 15368, "name": "formal/tlc", "headSha": SHA, "status": "completed", "conclusion": "failure",
         "externalId": None},
        {"id": 6, "appId": 15368, "name": "formal/lean", "headSha": SHA, "status": "completed", "conclusion": "failure",
         "externalId": "77"}]
    assert reader.annotations("owner/repo", 5) == [{"title": "formal/tlc positive_violation", "message": "{}"}]
    assert transport.paths == [f"/repos/owner/repo/commits/{SHA}/check-runs?filter=latest&per_page=100",
                               "/repos/owner/repo/check-runs/5/annotations?per_page=50"]


def trusted(external="42"):
    return {"id": 9, "name": "formal-trusted/lean", "headSha": SHA, "externalId": external}


def workflow_run(path=".github/workflows/formal-trusted.yml", event="pull_request_target"):
    return {"id": 42, "path": path, "event": event, "head_branch": "main", "conclusion": "success"}


def test_trusted_provenance_requires_base_workflow_event_and_head_bound_artifact():
    bound = {"artifacts": [{"name": f"formal-trusted-{SHA}"}]}
    transport = Transport([workflow_run(), bound])
    proof = GitHubFormalCheckReader(transport).provenance("owner/repo", trusted())
    assert proof["verified"] is True and proof["runId"] == 42 and proof["event"] == "pull_request_target"
    assert transport.paths == ["/repos/owner/repo/actions/runs/42", "/repos/owner/repo/actions/runs/42/artifacts?per_page=100"]
    cases = [([workflow_run(path=".github/workflows/formal.yml")], "untrusted_workflow"),
             ([workflow_run(event="pull_request")], "untrusted_event"),
             ([workflow_run(), {"artifacts": [{"name": "formal-trusted-" + "b" * 40}]}], "head_not_bound")]
    for responses, reason in cases:
        assert GitHubFormalCheckReader(Transport(responses)).provenance("owner/repo", trusted())["reason"] == reason
    empty = Transport([])
    assert GitHubFormalCheckReader(empty).provenance("owner/repo", trusted("../1"))["reason"] == "missing_run_id"
    assert empty.paths == []


@pytest.mark.parametrize("repository,sha", [("owner/../x", SHA), ("owner", SHA), ("owner/repo", "HEAD")])
def test_invalid_identity_is_rejected_before_any_read(repository, sha):
    transport = Transport([])
    with pytest.raises(GitHubReadError):
        GitHubFormalCheckReader(transport).checks(repository, sha)
    assert transport.paths == []


def test_check_for_other_sha_is_malformed():
    reader = GitHubFormalCheckReader(Transport([{"check_runs": [run(sha="b" * 40)]}]))
    with pytest.raises(GitHubReadError):
        reader.checks("owner/repo", SHA)
