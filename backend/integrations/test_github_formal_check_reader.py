"""`formal/tlc` reader builds fixed GET paths and validates GitHub JSON offline."""
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
    transport = Transport([{"total_count": 2, "check_runs": [run(), run(name="formal/tlc-other")]},
                           [{"title": "formal/tlc positive_violation", "message": "{}"}]])
    reader = GitHubFormalCheckReader(transport)
    assert reader.checks("owner/repo", SHA) == [{"id": 5, "appId": 15368, "name": "formal/tlc", "headSha": SHA,
                                                 "status": "completed", "conclusion": "failure"}]
    assert reader.annotations("owner/repo", 5) == [{"title": "formal/tlc positive_violation", "message": "{}"}]
    assert transport.paths == [f"/repos/owner/repo/commits/{SHA}/check-runs?check_name=formal/tlc&filter=latest&per_page=10",
                               "/repos/owner/repo/check-runs/5/annotations?per_page=50"]


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
