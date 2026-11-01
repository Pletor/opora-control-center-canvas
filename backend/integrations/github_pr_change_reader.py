"""GET-only bounded read of a PR's changed files for the review risk tier (docs/oporahub-review-jobs.md).

Reuses the fixed-origin review transport (no redirects, no proxies, bounded bytes). The PR head
is checked before and after the file listing so the change belongs to the exact reviewed SHA.
Anything incomplete is reported as `complete: false`; the caller then fails closed.

`fingerprint` is the content of the change without its position: a clean rebase onto a moved base
keeps it, so the review of that content carries over (docs/oporahub-review-jobs.md)."""
import hashlib
import json
import re

from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport

NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
SHA = re.compile(r"[0-9a-f]{40}")
PAGE, MAX_PAGES = 100, 3
COMPARE_FILES = 300  # GitHub truncates the compare file list here; a full page may be incomplete.


def _patch_body(patch):
    """Diff lines without hunk headers, so a shifted line number does not change the content."""
    return "\n".join(line for line in patch.split("\n") if not line.startswith("@@"))


def patch_fingerprint(items):
    """sha256 over the sorted GitHub file records, or None when any file has neither patch nor blob sha."""
    entries = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            return None
        patch, blob = item.get("patch"), item.get("sha")
        if isinstance(patch, str):
            content = ["patch", _patch_body(patch)]
        elif isinstance(blob, str) and blob:
            content = ["blob", blob]
        else:
            return None
        previous = item.get("previous_filename")
        entries.append([item["filename"], previous if isinstance(previous, str) else None,
                        str(item.get("status") or ""), *content])
    entries.sort()
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False).encode("utf-8")).hexdigest()


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
        """`{complete, baseSha, files: [{path, additions, deletions}], fingerprint}`; never raises remotely."""
        if (not isinstance(repository, str) or NAME.fullmatch(repository) is None or ".." in repository
                or type(number) is not int or number < 1):
            return {"complete": False, "baseSha": None, "files": [], "error": "invalid-request"}
        try:
            head, base = self._pull(repository, number)
            if head != head_sha:
                return {"complete": False, "baseSha": base, "files": [], "error": "head-moved"}
            files, raw = [], []
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
                    raw.append(item)
                    previous = item.get("previous_filename")
                    if isinstance(previous, str) and previous != path:
                        files.append({"path": previous, "additions": 0, "deletions": 0})
                if len(items) < PAGE:
                    break
            else:
                return {"complete": False, "baseSha": base, "files": files, "error": "too-many-files"}
            if self._pull(repository, number)[0] != head_sha:
                return {"complete": False, "baseSha": base, "files": [], "error": "head-moved"}
            return {"complete": True, "baseSha": base, "files": files, "fingerprint": patch_fingerprint(raw)}
        except (GitHubReadError, ValueError, TypeError, AttributeError):
            return {"complete": False, "baseSha": None, "files": [], "error": "github-unavailable"}

    def fingerprint(self, repository, base_sha, head_sha):
        """Content fingerprint of `base...head` for an older head (compare API); None on any failure."""
        if (not isinstance(repository, str) or NAME.fullmatch(repository) is None or ".." in repository
                or _sha(base_sha) is None or _sha(head_sha) is None):
            return None
        try:
            value = self._get(f"/repos/{repository}/compare/{base_sha}...{head_sha}")
            items = (value or {}).get("files")
            if not isinstance(items, list) or len(items) >= COMPARE_FILES:
                return None
            return patch_fingerprint(items)
        except (GitHubReadError, ValueError, TypeError, AttributeError):
            return None
