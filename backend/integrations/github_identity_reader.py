"""GET-only reader of PR/issue comments that carry a reviewer identity proof.

Reuses the bounded fixed-origin review transport (no redirects, no proxies, size limit).
Returns normalized comments; the caller decides whether one proves a claimed identity."""
import re

from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport

NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
PAGES, PER_PAGE, MAX_BODY = 3, 100, 4000


def _positive(value):
    return type(value) is int and value > 0


class GitHubIdentityReader:
    def __init__(self, transport=None):
        self.transport = transport or GitHubReviewTransport()

    def comments(self, repository, number):
        """Up to 300 comments of one PR/issue: [{id, login, userId, userType, body, createdAt, url}]."""
        if not isinstance(repository, str) or NAME.fullmatch(repository) is None or ".." in repository:
            raise GitHubReadError("Invalid GitHub repository.")
        if not _positive(number):
            raise GitHubReadError("Invalid pull request number.")
        result = []
        for page in range(1, PAGES + 1):
            items, _ = self.transport(f"/repos/{repository}/issues/{number}/comments?per_page={PER_PAGE}&page={page}",
                                      timeout=10)
            if not isinstance(items, list) or len(items) > PER_PAGE:
                raise GitHubReadError("Unexpected GitHub comment listing.")
            for item in items:
                user = item.get("user") if isinstance(item, dict) else None
                if not isinstance(user, dict) or not _positive(item.get("id")) or not _positive(user.get("id")):
                    continue
                body = item.get("body") if isinstance(item.get("body"), str) else ""
                result.append({"id": item["id"], "login": str(user.get("login", "")), "userId": user["id"],
                               "userType": user.get("type"), "body": body[:MAX_BODY],
                               "createdAt": item.get("created_at"), "url": item.get("html_url")})
            if len(items) < PER_PAGE:
                break
        return result
