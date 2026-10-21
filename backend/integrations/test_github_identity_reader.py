"""Identity proof reader: GET-only paths, bounded pages, malformed comments skipped."""
import pytest

from backend.integrations.github_identity_reader import GitHubIdentityReader
from backend.integrations.github_review_transport import GitHubReadError


def comment(index, user=None):
    return {"id": index, "user": user if user is not None else {"id": 7, "login": "Martin", "type": "User"},
            "body": "Opora-Identity: hi_x n", "created_at": "2026-10-21T10:00:00Z", "html_url": f"https://x/{index}"}


def test_reads_pages_until_short_and_normalizes():
    paths = []

    def transport(path, *, timeout):
        paths.append(path)
        page = int(path.rsplit("=", 1)[1])
        return ([comment(n) for n in range(1, 101)] if page == 1 else [comment(500), comment(501, {"id": "x"})]), {}

    items = GitHubIdentityReader(transport).comments("owner/repo", 3)
    assert paths == ["/repos/owner/repo/issues/3/comments?per_page=100&page=1",
                     "/repos/owner/repo/issues/3/comments?per_page=100&page=2"]
    assert len(items) == 101 and items[-1] == {"id": 500, "login": "Martin", "userId": 7, "userType": "User",
                                               "body": "Opora-Identity: hi_x n", "createdAt": "2026-10-21T10:00:00Z",
                                               "url": "https://x/500"}


@pytest.mark.parametrize("repository,number", [("../x", 1), ("owner/repo", 0), ("owner/repo", True)])
def test_rejects_invalid_targets(repository, number):
    with pytest.raises(GitHubReadError):
        GitHubIdentityReader(lambda *_, **__: ([], {})).comments(repository, number)


def test_unexpected_listing_fails():
    with pytest.raises(GitHubReadError):
        GitHubIdentityReader(lambda *_, **__: ({"message": "x"}, {})).comments("owner/repo", 1)
