"""PR identity/listing normalization; offline transport, GET paths only."""
import pytest

from backend.integrations.github_merge_transport import GitHubMergeError, GitHubMergeTransport
from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader

SHA = "a" * 40


def item(number=7, merged_at=None, state="open", body="Opora-Execution: x"):
    return {"id": 100 + number, "number": number, "state": state, "merged_at": merged_at, "body": body,
            "base": {"ref": "main", "repo": {"id": 1, "full_name": "Owner/Repo"}},
            "head": {"ref": "feature", "sha": SHA, "repo": {"id": 2}}}


def reader(responses):
    paths = []

    def transport(path, *, timeout):
        paths.append(path)
        return responses[path], {}
    return GitHubPullRequestLinkReader(transport, sleep=lambda _: None), paths


def test_recent_and_single_pull_request_identity():
    listing = "/repos/owner/repo/pulls?state=all&sort=updated&direction=desc&per_page=20"
    subject, paths = reader({"/repos/owner/repo": {"id": 1, "full_name": "Owner/Repo"},
                             listing: [item(), item(8, "2026-10-20T10:00:00Z", "closed"), item(9, None, "closed")],
                             "/repos/owner/repo/pulls/7": item()})
    states = [(pr["number"], pr["state"], pr["headRepoId"]) for pr in subject.recent("owner/repo")]
    assert states == [(7, "open", 2), (8, "merged", 2), (9, "closed", 2)]
    single = subject.pull_request("owner/repo", 7)
    assert single["repository"] == {"id": 1, "fullName": "owner/repo"} and single["id"] == 107
    assert paths == ["/repos/owner/repo", listing, "/repos/owner/repo", "/repos/owner/repo/pulls/7"]


def test_foreign_repository_is_identity_mismatch():
    subject, _ = reader({"/repos/owner/repo": {"id": 1, "full_name": "owner/repo"},
                         "/repos/owner/repo/pulls/7": {**item(), "base": {"ref": "main", "repo": {"id": 5, "full_name": "x/y"}}}})
    with pytest.raises(GitHubMergeError, match="identity"):
        subject.pull_request("owner/repo", 7)


def test_transport_only_allows_the_bounded_listing_path():
    transport = GitHubMergeTransport(opener=object())
    for path in ("/repos/o/r/pulls?state=open", "/repos/o/r/pulls?state=all&sort=updated&direction=desc&per_page=500",
                 "/repos/o/r/issues"):
        with pytest.raises(GitHubMergeError, match="invalid-read-request"):
            transport(path, timeout=1)
