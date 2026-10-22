"""GET-only reader of the formal check runs, their annotations and trusted-run provenance.

Reuses the fixed-origin review transport (no redirects, no proxies, bounded bytes).
Never writes to GitHub. Used by backend/canvas/opora_formal_check_poll.py."""
import re

from backend.integrations import github_review_normalize as normalize
from backend.integrations.github_review_transport import GitHubReviewTransport

CHECK_NAMES = ("formal/tlc", "formal/lean", "formal/conformance", "formal-trusted/tlc", "formal-trusted/lean")
TRUSTED_WORKFLOW = ".github/workflows/formal-trusted.yml"
TRUSTED_EVENTS = ("pull_request_target", "workflow_run")
REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
RUN_ID = re.compile(r"[1-9][0-9]{0,18}")
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
        """Latest normalized formal check runs on `sha` (evidence snapshot shape + `externalId`)."""
        repository, sha = self._repository(repository), normalize.sha(sha)
        data, _ = self.transport(f"/repos/{repository}/commits/{sha}/check-runs?filter=latest&per_page=100",
                                 timeout=self.timeout)
        runs = normalize.obj(data).get("check_runs")
        normalize.require(isinstance(runs, list) and len(runs) <= 100)
        result = []
        for item in runs:
            check = normalize.check(item, sha)
            if check["name"] in CHECK_NAMES:
                external = item.get("external_id")
                result.append({**check, "externalId": external if isinstance(external, str) else None})
        return result

    def annotations(self, repository, check_id):
        repository, check_id = self._repository(repository), normalize.positive(check_id)
        data, _ = self.transport(f"/repos/{repository}/check-runs/{check_id}/annotations?per_page={MAX_ANNOTATIONS}",
                                 timeout=self.timeout)
        normalize.require(isinstance(data, list))
        return [{"title": str(normalize.obj(item).get("title") or "")[:200],
                 "message": str(item.get("message") or "")[:4000]} for item in data[:MAX_ANNOTATIONS]]

    def provenance(self, repository, check):
        """Bind a `formal-trusted/*` check to a base-branch workflow run of this PR head.

        The publishing job puts its run id into the check's `external_id`. The run must come from
        the trusted workflow file, triggered by pull_request_target or workflow_run (so GitHub took
        the definition from the base branch), and own the artifact `formal-trusted-<headSha>`,
        which only that run could upload. Anything else is `verified: False` with a reason."""
        repository, run_id = self._repository(repository), check.get("externalId")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            return {"verified": False, "reason": "missing_run_id"}
        run, _ = self.transport(f"/repos/{repository}/actions/runs/{run_id}", timeout=self.timeout)
        run = normalize.obj(run)
        facts = {"runId": int(run_id), "event": run.get("event"), "path": run.get("path"),
                 "headBranch": run.get("head_branch")}
        if str(facts["path"] or "").split("@")[0] != TRUSTED_WORKFLOW:
            return {"verified": False, "reason": "untrusted_workflow", **facts}
        if facts["event"] not in TRUSTED_EVENTS:
            return {"verified": False, "reason": "untrusted_event", **facts}
        artifacts, _ = self.transport(f"/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
                                      timeout=self.timeout)
        names = {item.get("name") for item in normalize.obj(artifacts).get("artifacts") or [] if isinstance(item, dict)}
        if f"formal-trusted-{check['headSha']}" not in names:
            return {"verified": False, "reason": "head_not_bound", **facts}
        return {"verified": True, "reason": None, **facts}
