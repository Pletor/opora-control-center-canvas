"""GET-only PR identity and bounded recent-PR listing for execution loop closure.

Reuses the fixed-origin lifecycle transport (no redirects, no proxies, bounded bytes,
sanitized rate-limit metadata). Never writes to GitHub."""
import re
import time

from backend.integrations.github_merge_reader import positive, require, sha
from backend.integrations.github_merge_transport import (
    GitHubMergeError,
    GitHubMergeTransport,
    cooldown,
)

NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
MAX_BODY = 20_000


def identity(value, repository):
    """Numeric identity of one PR (list item or single PR payload) within the configured repository."""
    require(isinstance(value, dict))
    base, head = value.get("base"), value.get("head")
    require(isinstance(base, dict) and isinstance(head, dict) and isinstance(base.get("repo"), dict))
    require(str(base["repo"].get("full_name", "")).casefold() == repository["fullName"]
            and positive(base["repo"].get("id")) == repository["id"], identity=True)
    fork = head.get("repo")
    require(fork is None or isinstance(fork, dict))
    ref, branch = head.get("ref"), base.get("ref")
    require(isinstance(ref, str) and 1 <= len(ref) <= 255 and isinstance(branch, str) and 1 <= len(branch) <= 255)
    state, merged_at = value.get("state"), value.get("merged_at")
    require(state in ("open", "closed") and (merged_at is None or isinstance(merged_at, str)))
    body = value.get("body")
    return {"repository": dict(repository), "id": positive(value.get("id")), "number": positive(value.get("number")),
            "baseRef": branch, "headRef": ref, "headSha": sha(head.get("sha")),
            "headRepoId": positive(fork.get("id")) if fork is not None else None,
            "state": "open" if state == "open" else "merged" if merged_at else "closed",
            "body": body[:MAX_BODY] if isinstance(body, str) else ""}


class GitHubPullRequestLinkReader:
    deadline_seconds = 25
    page_size = 20

    def __init__(self, transport=None, *, monotonic=time.monotonic, sleep=time.sleep):
        self.transport, self.monotonic, self.sleep = transport or GitHubMergeTransport(), monotonic, sleep
        self.retry_after, self.last_call = 0, None

    def _get(self, path, start):
        if self.last_call is not None:
            self.sleep(max(0, self.last_call + 1 - self.monotonic()))
        remaining = self.deadline_seconds - (self.monotonic() - start)
        if remaining <= 0:
            raise GitHubMergeError("github-timeout")
        self.last_call = self.monotonic()
        data, headers = self.transport(path, timeout=min(8, remaining))
        self.retry_after = max(self.retry_after, cooldown(headers))
        return data

    def _repository(self, full_name, start):
        require(isinstance(full_name, str) and NAME.fullmatch(full_name) is not None and ".." not in full_name)
        actual = self._get("/repos/" + full_name, start)
        require(isinstance(actual, dict) and str(actual.get("full_name", "")).casefold() == full_name.casefold(),
                identity=True)
        return {"id": positive(actual.get("id")), "fullName": full_name.casefold()}

    def pull_request(self, full_name, number):
        start, self.retry_after = self.monotonic(), 0
        repository = self._repository(full_name, start)
        positive(number)
        return identity(self._get(f"/repos/{full_name}/pulls/{number}", start), repository)

    def recent(self, full_name):
        """One bounded page of most recently updated PRs (any state) with their bodies."""
        start, self.retry_after = self.monotonic(), 0
        repository = self._repository(full_name, start)
        items = self._get(f"/repos/{full_name}/pulls?state=all&sort=updated&direction=desc&per_page={self.page_size}",
                          start)
        require(isinstance(items, list) and len(items) <= self.page_size)
        return [identity(item, repository) for item in items]
