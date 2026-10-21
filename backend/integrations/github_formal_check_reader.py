"""GET-only reader of the `formal/tlc` check run and its annotations for one commit.

Reuses the fixed-origin review transport (no redirects, no proxies, bounded bytes).
Never writes to GitHub. Used by backend/canvas/opora_formal_check_poll.py."""
import re

from backend.integrations import github_review_normalize as normalize
from backend.integrations.github_review_transport import GitHubReviewTransport

CHECK_NAME = "formal/tlc"
REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
MAX_ANNOTATIONS = 50


class GitHubFormalCheckReader:
    timeout = 10

    def __init__(self, transport=None):
        self.transport = transport or GitHubReviewTransport()

    @staticmethod
    def _repository(value):
        normalize.require(isinstance(value, str) and REPOSITORY.fullmatch(value) is not None and ".." not in value)
        return value

    def checks(self, repository, sha):
        """Latest normalized `formal/tlc` check runs on `sha` (same shape as evidence snapshots)."""
        repository, sha = self._repository(repository), normalize.sha(sha)
        data, _ = self.transport(f"/repos/{repository}/commits/{sha}/check-runs?check_name={CHECK_NAME}"
                                 "&filter=latest&per_page=10", timeout=self.timeout)
        runs = normalize.obj(data).get("check_runs")
        normalize.require(isinstance(runs, list) and len(runs) <= 10)
        return [check for check in (normalize.check(item, sha) for item in runs) if check["name"] == CHECK_NAME]

    def annotations(self, repository, check_id):
        repository, check_id = self._repository(repository), normalize.positive(check_id)
        data, _ = self.transport(f"/repos/{repository}/check-runs/{check_id}/annotations?per_page={MAX_ANNOTATIONS}",
                                 timeout=self.timeout)
        normalize.require(isinstance(data, list))
        return [{"title": str(normalize.obj(item).get("title") or "")[:200],
                 "message": str(item.get("message") or "")[:4000]} for item in data[:MAX_ANNOTATIONS]]
