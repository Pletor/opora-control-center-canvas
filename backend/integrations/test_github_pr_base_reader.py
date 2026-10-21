"""Base freshness reading: GET-only compare against the current base head, bound to the exact PR head."""
import pytest

from backend.integrations.github_pr_base_reader import GitHubPullRequestBaseReader
from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport
from backend.integrations.test_github_review_transport import Opener

HEAD, TIP, OLD = "a" * 40, "b" * 40, "c" * 40
COMPARE = f"/repos/owner/repo/compare/release/1.x...{HEAD}"


def pull(head=HEAD, ref="release/1.x", body="## Testing\nok\n## Risk\n<!-- hint -->\n"):
    return {"head": {"sha": head}, "base": {"ref": ref, "sha": OLD}, "body": body}


def compare(merge_base=TIP, behind=0):
    return {"base_commit": {"sha": TIP}, "merge_base_commit": {"sha": merge_base}, "behind_by": behind, "ahead_by": 2}


def reader(responses):
    paths = []

    def transport(path, *, timeout):
        paths.append(path)
        value = responses[path]
        if isinstance(value, Exception):
            raise value
        return value, {}
    return GitHubPullRequestBaseReader(transport), paths


def test_fresh_and_stale_heads_against_the_current_base_tip():
    subject, paths = reader({"/repos/owner/repo/pulls/7": pull(), COMPARE: compare()})
    assert subject.base("owner/repo", 7, HEAD) == {
        "complete": True, "baseRef": "release/1.x", "baseSha": TIP, "mergeBaseSha": TIP, "behindBy": 0, "aheadBy": 2,
        "sections": ["testing"]}
    assert paths == ["/repos/owner/repo/pulls/7", COMPARE]
    subject, _ = reader({"/repos/owner/repo/pulls/7": pull(), COMPARE: compare(OLD, 4)})
    stale = subject.base("owner/repo", 7, HEAD)
    assert (stale["mergeBaseSha"], stale["behindBy"]) == (OLD, 4)


@pytest.mark.parametrize(("responses", "error"), [
    ({"/repos/owner/repo/pulls/7": pull("d" * 40)}, "head-moved"),
    ({"/repos/owner/repo/pulls/7": pull(ref="a/../b")}, "invalid-base-ref"),
    ({"/repos/owner/repo/pulls/7": pull(ref="-x")}, "invalid-base-ref"),
    ({"/repos/owner/repo/pulls/7": pull(), COMPARE: {"behind_by": 0}}, "invalid-compare"),
    ({"/repos/owner/repo/pulls/7": pull(), COMPARE: compare(behind=-1)}, "invalid-compare"),
    ({"/repos/owner/repo/pulls/7": GitHubReadError()}, "github-unavailable"),
])
def test_anything_unexpected_is_incomplete(responses, error):
    subject, _ = reader(responses)
    assert subject.base("owner/repo", 7, HEAD) == {"complete": False, "error": error}


def test_invalid_requests_never_read():
    subject, paths = reader({})
    assert subject.base("owner/../repo", 7, HEAD)["error"] == "invalid-request"
    assert subject.base("owner/repo", 7, "HEAD")["error"] == "invalid-request"
    assert paths == []


def test_transport_allows_only_the_exact_compare_form():
    opener = Opener(b'{"behind_by": 0}')
    GitHubReviewTransport(opener=opener)(COMPARE, timeout=10)
    assert opener.calls[0][0].full_url == "https://api.github.com" + COMPARE
    for path in (f"/repos/owner/repo/compare/a/../b...{HEAD}", "/repos/owner/repo/compare/main...main",
                 f"/repos/owner/../compare/main...{HEAD}", f"/repos/owner/repo/compare/main....{HEAD}",
                 f"/repos/owner/repo/compare//main...{HEAD}"):
        with pytest.raises(GitHubReadError):
            GitHubReviewTransport(opener=Opener())(path, timeout=10)
