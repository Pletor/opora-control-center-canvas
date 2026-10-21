"""Reverts and incidents of reviewed PRs become an immutable eval set (docs/oporahub-review-identity.md).

A revert is a PR whose body carries exactly one `Opora-Revert-Of: #<n>` trailer pointing at a
reviewed PR of the configured repository (read with the same GET-only recent-PR listing as
loop closure). An incident is linked explicitly. Each link deterministically creates one eval
case (diff ref, base/head/merge SHA, revert SHA, findings that existed); repeating the link or
the sync never creates a second case and never rewrites the first."""
import json
import re

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_pr_enrollment import configured
from backend.canvas.opora_review_aggregation import short_id
from backend.canvas.opora_review_insight_common import (
    InsightMissing,
    fields,
    number,
    project_id,
    reading,
    repository,
    text,
    workspace_id,
    writing,
)

REVERT = re.compile(r"^[ \t>]*opora-revert-of:[ \t]*(?:([A-Za-z0-9-]+/[A-Za-z0-9_.-]+)#|#)?([0-9]{1,9})[ \t]*$",
                    re.IGNORECASE | re.MULTILINE)
SCHEMA_VERSION = 1


def parse_revert(body, configured_repository):
    """Reverted PR number or None unless exactly one trailer names this repository (or no repository)."""
    if not isinstance(body, str):
        return None
    found = {(repo.casefold() if repo else configured_repository, int(value))
             for repo, value in REVERT.findall(body.replace("\r\n", "\n"))}
    if len(found) != 1:
        return None
    repo, value = found.pop()
    return value if repo == configured_repository and value > 0 else None


def reviewed(db, project, repo, pr_number):
    """Jobs of one PR across every workspace, oldest first."""
    rows = db.execute("SELECT workspace_id,base_sha,head_sha,phase,round,candidates FROM opora_review_jobs WHERE "
                      "project_id=? AND repository=? AND number=? ORDER BY created_at,job_id",
                      (project, repo, pr_number)).fetchall()
    return [dict(zip(("workspace", "baseSha", "headSha", "phase", "round", "candidates"), row)) for row in rows]


def case_content(db, project, repo, pr_number, kind, source, extra):
    jobs = reviewed(db, project, repo, pr_number)
    done = [job for job in jobs if job["phase"] == "completed"] or jobs
    base = next((job["baseSha"] for job in jobs if job["baseSha"]), None)
    head = done[-1]["headSha"]
    merge = db.execute("SELECT merge_sha FROM opora_execution_pull_requests WHERE project_id=? AND repository=? AND "
                       "number=? AND merge_sha IS NOT NULL ORDER BY updated_at DESC LIMIT 1",
                       (project, repo, pr_number)).fetchone()
    findings = db.execute("SELECT fingerprint,severity,status,round,content FROM opora_review_findings WHERE "
                          "project_id=? AND repository=? AND number=? ORDER BY round,fingerprint",
                          (project, repo, pr_number)).fetchall()
    rejected = sorted({item["fingerprint"] for job in done if job["phase"] == "completed"
                       for item in json.loads(job["candidates"])
                       if item.get("kind") == "finding" and item.get("accepted") is False})
    return jobs[0]["workspace"], {
        "schemaVersion": SCHEMA_VERSION, "caseId": short_id("rev_", project, repo, pr_number, kind, source),
        "kind": kind, "repository": repo, "number": pr_number, "workspace": jobs[0]["workspace"],
        "diffRef": {"repository": repo, "base": base, "head": head, "range": f"{base or 'merge-base'}..{head}",
                    "url": f"https://github.com/{repo}/pull/{pr_number}/files"},
        "baseSha": base, "headSha": head, "mergeSha": merge[0] if merge else None,
        "rounds": sum(job["phase"] == "completed" for job in jobs),
        "findings": [{"fingerprint": fp, "severity": severity, "status": status, "round": round_,
                      **{key: json.loads(content).get(key) for key in ("path", "line", "title")}}
                     for fp, severity, status, round_, content in findings],
        "rejectedFingerprints": rejected, **extra}


def ensure_case(db, store, project, repo, pr_number, kind, source, extra):
    """Create the eval case once; returns (caseId, created)."""
    workspace, content = case_content(db, project, repo, pr_number, kind, source, extra)
    content["createdAt"] = stamp()
    created = store.insert_case(workspace, content["caseId"], repo, pr_number, kind, source, content,
                                content["createdAt"])
    return content["caseId"], created


class ReviewEvals:
    def __init__(self, canvas, reader=None):
        self.canvas, self._reader = canvas, reader

    @property
    def reader(self):
        if self._reader is None:
            from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader
            self._reader = GitHubPullRequestLinkReader()
        return self._reader

    def link_incident(self, payload, actor):
        fields(payload, ("project", "workspace", "repository", "number", "reference", "summary"))
        project, workspace = project_id(payload["project"]), workspace_id(payload["workspace"])
        repo, pr_number = repository(payload["repository"]), number(payload["number"])
        reference, summary = text(payload["reference"], "Odkaz", 300), text(payload["summary"], "Shrnutí", 2000)
        with writing(self.canvas, project) as (db, store):
            if not reviewed(db, project, repo, pr_number):
                raise InsightMissing("PR nemá žádné automatické review.")
            incident_id = short_id("ri_", project, repo, pr_number, reference)
            store.insert_incident(workspace, incident_id, repo, pr_number, reference, summary, actor, stamp())
            case_id, created = ensure_case(db, store, project, repo, pr_number, "incident", incident_id, {
                "revertSha": None, "revertNumber": None, "incident": {"reference": reference, "summary": summary}})
        return {"incidentId": incident_id, "caseId": case_id, "created": created}

    def sync_reverts(self, payload):
        """Read one page of recent PRs (outside locks) and record merged reverts of reviewed PRs."""
        fields(payload, ("project",))
        project = project_id(payload["project"])
        config = configured(self.canvas, project)
        if config is None:
            return {"reverts": [], "created": []}
        repo = config["repository"].casefold()
        observed = [(parse_revert(pr.get("body"), repo), pr) for pr in self.reader.recent(config["repository"])]
        observed = [(target, pr) for target, pr in observed if target and pr.get("state") == "merged"
                    and target != pr.get("number")]
        reverts, created = [], []
        with writing(self.canvas, project) as (db, store):
            for target, pr in sorted(observed, key=lambda item: (item[0], item[1]["number"])):
                if not reviewed(db, project, repo, target):
                    continue
                store.insert_revert(repo, target, pr["number"], pr["headSha"], stamp())
                case_id, new = ensure_case(db, store, project, repo, target, "revert", f"#{pr['number']}", {
                    "revertSha": pr["headSha"], "revertNumber": pr["number"], "incident": None})
                reverts.append({"number": target, "revertNumber": pr["number"], "caseId": case_id})
                if new:
                    created.append(case_id)
        return {"reverts": reverts, "created": created}

    def list(self, project, workspace=None):
        project, workspace = project_id(project), workspace_id(workspace, nullable=True)
        with reading(self.canvas, project) as (_, store):
            return {"items": store.cases(workspace)}

    def export_jsonl(self, project, workspace=None):
        return "".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                       for item in self.list(project, workspace)["items"])
