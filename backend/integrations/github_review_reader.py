"""Read a bounded GitHub observation, never infer review approval or authorize merge."""
import re
import time
from datetime import UTC, datetime
from urllib.parse import quote

from backend.integrations import github_review_normalize as normalize
from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport

MAX_PAGES = 10
MAX_REQUESTS = 80
DEADLINE_SECONDS = 60


class _Collection:
    def __init__(self, transport):
        self.transport = transport
        self.deadline = time.monotonic() + DEADLINE_SECONDS
        self.requests = 0

    def get(self, path):
        self.requests += 1
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or self.requests > MAX_REQUESTS:
            raise GitHubReadError("GitHub observation exceeded its time or request limit.")
        result = self.transport(path, timeout=remaining)
        if time.monotonic() > self.deadline:
            raise GitHubReadError("GitHub observation exceeded its time limit.")
        return result

    def pages(self, path, *, key=None):
        items, seen, expected_total = [], set(), None
        for page in range(1, MAX_PAGES + 1):
            separator = "&" if "?" in path else "?"
            data, headers = self.get(f"{path}{separator}per_page=100&page={page}")
            if key:
                normalize.obj(data)
                total = data.get("total_count")
                normalize.require(type(total) is int and 0 <= total <= MAX_PAGES * 100)
                normalize.require(expected_total is None or expected_total == total)
                expected_total = total
                data = data.get(key)
            normalize.require(isinstance(data, list) and len(data) <= 100)
            for item in data:
                identifier = normalize.positive(normalize.obj(item).get("id"))
                normalize.require(identifier not in seen)
                seen.add(identifier)
            items.extend(data)
            # Never follow Link URLs (even same-origin); construct every page locally.
            link = headers.get("link", headers.get("Link", ""))
            normalize.require(isinstance(link, str))
            more = bool(re.search(r'rel\s*=\s*["\']?next\b', link))
            if not more and len(data) < 100:
                normalize.require(expected_total is None or len(items) == expected_total)
                return items
            if not data:
                raise GitHubReadError("GitHub pagination is incomplete.")
        raise GitHubReadError("GitHub pagination exceeded the observation limit.")


class GitHubReviewReader:
    def __init__(self, *, transport=None):
        self.transport = transport or GitHubReviewTransport()

    def read(self, repository: str, pr_number: int) -> dict:
        normalize.require(isinstance(repository, str) and normalize.REPOSITORY.fullmatch(repository)
                          and ".." not in repository)
        normalize.positive(pr_number)
        collection = _Collection(self.transport)
        root = "/repos/" + repository
        repo = normalize.repository(collection.get(root)[0], repository)
        pr_path = f"{root}/pulls/{pr_number}"
        before = normalize.pull(collection.get(pr_path)[0], repo, pr_number)
        reviews = [normalize.review(item) for item in collection.pages(pr_path + "/reviews")]
        permissions = {}
        for item in reviews:
            identity = (item["userId"], item["login"])
            if identity not in permissions:
                permissions[identity] = self._permission(collection, root, item)
            item["permission"] = permissions[identity]
        commit_path = f"{root}/commits/{before['headSha']}"
        checks = [normalize.check(item, before["headSha"]) for item in
                  collection.pages(commit_path + "/check-runs?filter=all", key="check_runs")]
        statuses = [normalize.status(item, before["headSha"]) for item in
                    collection.pages(commit_path + "/statuses")]
        after = normalize.pull(collection.get(pr_path)[0], repo, pr_number)
        normalize.require(before == after)
        return {"repository": repo, "pr": before, "reviews": reviews, "checks": checks,
                "statuses": statuses, "complete": True, "observedAt": datetime.now(UTC).isoformat()}

    @staticmethod
    def _permission(collection, root, reviewer):
        if reviewer["userType"] != "User":
            return "unknown"
        try:
            value = collection.get(root + "/collaborators/" + quote(reviewer["login"], safe="") + "/permission")[0]
        except GitHubReadError as error:
            if error.status in (403, 404):
                return "unknown"
            raise
        normalize.obj(value)
        user = value.get("user")
        if user is None or value.get("permission") is None:
            return "unknown"
        normalize.obj(user)
        normalize.require(normalize.positive(user.get("id")) == reviewer["userId"] and
                          str(user.get("login", "")).casefold() == reviewer["login"].casefold())
        permission = value["permission"]
        return permission if permission in ("admin", "maintain", "write", "push", "read", "triage", "none") else "unknown"
