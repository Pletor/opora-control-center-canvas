"""GET-only read of a PR head against the CURRENT base branch head (docs/oporahub-review-jobs.md, "Fronta merge").

Reads the PR (head, base ref, body) and the compare API `base_ref...head_sha`: `base_commit` is the
current tip of the base branch, `merge_base_commit` the merge-base of the head with it. The head is
fresh exactly when the merge-base equals the tip (`behind_by == 0`). The PR body is reduced to the
names of filled sections; the body itself is not stored. Never raises for remote failures."""
import re
from urllib.parse import quote

from backend.canvas.opora_review_template import filled_sections
from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport

NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
REF = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}")
SHA = re.compile(r"[0-9a-f]{40}")


def _sha(value):
    return value if isinstance(value, str) and SHA.fullmatch(value) else None


def _ref(value):
    ok = (isinstance(value, str) and REF.fullmatch(value) and ".." not in value and "//" not in value
          and not value.endswith(("/", ".", ".lock")))
    return value if ok else None


class GitHubPullRequestBaseReader:
    def __init__(self, transport=None):
        self.transport = transport or GitHubReviewTransport()

    def _get(self, path):
        data, _ = self.transport(path, timeout=10)
        return data

    def base(self, repository, number, head_sha):
        """`{complete, baseRef, baseSha, mergeBaseSha, behindBy, aheadBy, sections}` or `{complete: False, error}`."""
        if (not isinstance(repository, str) or NAME.fullmatch(repository) is None or ".." in repository
                or type(number) is not int or number < 1 or _sha(head_sha) is None):
            return {"complete": False, "error": "invalid-request"}
        try:
            pull = self._get(f"/repos/{repository}/pulls/{number}") or {}
            if _sha((pull.get("head") or {}).get("sha")) != head_sha:
                return {"complete": False, "error": "head-moved"}
            ref = _ref((pull.get("base") or {}).get("ref"))
            if ref is None:
                return {"complete": False, "error": "invalid-base-ref"}
            body = pull.get("body")
            compare = self._get(f"/repos/{repository}/compare/{quote(ref, safe='/')}...{head_sha}") or {}
            tip = _sha((compare.get("base_commit") or {}).get("sha"))
            merge_base = _sha((compare.get("merge_base_commit") or {}).get("sha"))
            behind, ahead = compare.get("behind_by"), compare.get("ahead_by")
            if tip is None or merge_base is None or type(behind) is not int or type(ahead) is not int or behind < 0:
                return {"complete": False, "error": "invalid-compare"}
            return {"complete": True, "baseRef": ref, "baseSha": tip, "mergeBaseSha": merge_base,
                    "behindBy": behind, "aheadBy": ahead,
                    "sections": filled_sections(body if isinstance(body, str) else "")}
        except (GitHubReadError, ValueError, TypeError, AttributeError):
            return {"complete": False, "error": "github-unavailable"}
