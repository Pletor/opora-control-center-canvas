"""GET-only bounded read of a PR's changed files for the review risk tier (docs/oporahub-review-jobs.md).

Reuses the fixed-origin review transport (no redirects, no proxies, bounded bytes). The PR head
is checked before and after the file listing so the change belongs to the exact reviewed SHA.
Anything incomplete is reported as `complete: false`; the caller then fails closed."""
import re

from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport

NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
SHA = re.compile(r"[0-9a-f]{40}")
PAGE, MAX_PAGES = 100, 3


def _sha(value):
    return value if isinstance(value, str) and SHA.fullmatch(value) else None


class GitHubPullRequestChangeReader:
    def __init__(self, transport=None):
        self.transport = transport or GitHubReviewTransport()

    def _get(self, path):
        data, _ = self.transport(path, timeout=10)
        return data

    def _pull(self, repository, number):
        value = self._get(f"/repos/{repository}/pulls/{number}")
        head, base = (value or {}).get("head") or {}, (value or {}).get("base") or {}
        return _sha(head.get("sha")), _sha(base.get("sha"))

    def change(self, repository, number, head_sha):
        """`{complete, baseSha, files: [{path, additions, deletions}]}`; never raises for remote failures."""
        if (not isinstance(repository, str) or NAME.fullmatch(repository) is None or ".." in repository
                or type(number) is not int or number < 1):
            return {"complete": False, "baseSha": None, "files": [], "error": "invalid-request"}
        try:
            head, base = self._pull(repository, number)
            if head != head_sha:
                return {"complete": False, "baseSha": base, "files": [], "error": "head-moved"}
            files = []
            for page in range(1, MAX_PAGES + 1):
                items = self._get(f"/repos/{repository}/pulls/{number}/files?per_page={PAGE}&page={page}")
                if not isinstance(items, list):
                    raise GitHubReadError()
                for item in items:
                    path = item.get("filename") if isinstance(item, dict) else None
                    added, removed = (item or {}).get("additions"), (item or {}).get("deletions")
                    if not isinstance(path, str) or type(added) is not int or type(removed) is not int:
                        raise GitHubReadError()
                    files.append({"path": path, "additions": added, "deletions": removed})
                    previous = item.get("previous_filename")
                    if isinstance(previous, str) and previous != path:
                        files.append({"path": previous, "additions": 0, "deletions": 0})
                if len(items) < PAGE:
                    break
            else:
                return {"complete": False, "baseSha": base, "files": files, "error": "too-many-files"}
            if self._pull(repository, number)[0] != head_sha:
                return {"complete": False, "baseSha": base, "files": [], "error": "head-moved"}
            return {"complete": True, "baseSha": base, "files": files}
        except (GitHubReadError, ValueError, TypeError, AttributeError):
            return {"complete": False, "baseSha": None, "files": [], "error": "github-unavailable"}
