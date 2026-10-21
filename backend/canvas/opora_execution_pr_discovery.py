"""Discover execution PRs from body trailers; one bounded read-only GitHub GET per project.

A PR body links itself to an execution with exactly one pair of trailer lines:

    Opora-Execution: <executionId>
    Opora-Revision: <acceptedRevision>

Both must match a stored, still unlinked execution of the configured repository and
base branch. Ambiguous or mismatched trailers are ignored; nothing is guessed."""
import re

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_pr_closure import close_loop
from backend.canvas.opora_execution_pr_enrollment import apply_enrollment, configured
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions

EXECUTION = re.compile(r"^[ \t>]*opora-execution:[ \t]*(\S+)[ \t]*$", re.IGNORECASE | re.MULTILINE)
REVISION = re.compile(r"^[ \t>]*opora-revision:[ \t]*(\S+)[ \t]*$", re.IGNORECASE | re.MULTILINE)


def parse_trailers(body):
    """Return (executionId, acceptedRevision) or None unless both trailers are present and unambiguous."""
    if not isinstance(body, str):
        return None
    text = body.replace("\r\n", "\n")
    executions, revisions = set(EXECUTION.findall(text)), set(REVISION.findall(text))
    if len(executions) != 1 or len(revisions) != 1:
        return None
    execution, revision = executions.pop(), revisions.pop()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", execution) is None or re.fullmatch(r"[a-f0-9]{40}", revision) is None:
        return None
    return execution, revision


def candidates(db, project, limit=200):
    """Most recent executions without a PR link: {executionId: workspaceId}."""
    rows = db.execute("SELECT e.id,e.workspace_id FROM opora_executions e WHERE e.project_id=? AND NOT EXISTS ("
                      "SELECT 1 FROM opora_execution_pull_requests l WHERE l.project_id=e.project_id "
                      "AND l.workspace_id=e.workspace_id AND l.execution_id=e.id) ORDER BY e.rowid DESC LIMIT ?",
                      (project, limit)).fetchall()
    return {row[0]: row[1] for row in rows}


def link_discovered(service, db, project, workspace, execution_id, revision, pr, config):
    """Caller holds locks and BEGIN IMMEDIATE. Returns the new link row or None when not applicable."""
    links = ExecutionPullRequests(db, project, workspace)
    if links.read(execution_id) is not None:
        return None
    try:
        record = Executions(db, project, workspace).read(execution_id)
    except ValueError:
        return None
    if (record["acceptedRevision"] != revision or pr["baseRef"] != config["branch"]
            or pr["repository"]["fullName"] != config["repository"]):
        return None
    now = stamp()
    row = links.insert({
        "execution_id": execution_id, "node_id": record["nodeId"], "accepted_revision": revision,
        "repository": config["repository"], "number": pr["number"], "head_ref": pr["headRef"],
        "head_sha": pr["headSha"], "state": "open", "binding_id": None, "enrollment": "pending",
        "enrollment_error": None, "enrollment_retry_at": None, "enrollment_failures": 0, "merge_sha": None,
        "merged_at": None, "awaiting_human_close": 0, "attention": None, "source": "discovery",
        "linked_by": "system", "created_at": now, "updated_at": now})
    row = apply_enrollment(service, links, row, pr)
    close_loop(db, project, workspace)
    return row


def discover(service, links, project):
    """Read one page of recent PRs and link matching executions. Returns linked execution IDs.

    `links` is an ExecutionPullRequestLinks (reader, guarded transaction). No GitHub request
    is made when the project has no GitHub repository or no unlinked execution."""
    config = configured(service, project)
    if config is None:
        return []
    with links.guard(), service.graph_lock_for(project), service.lock_for(project):
        pending = candidates(service.db_for(project), project)
    if not pending:
        return []
    linked = []
    for pr in links.reader.recent(config["repository"]):
        trailers = parse_trailers(pr.get("body"))
        if trailers is None or trailers[0] not in pending:
            continue
        execution_id, revision = trailers
        with links.transaction(project, pending[execution_id]) as repo:
            if link_discovered(service, repo.db, project, pending[execution_id], execution_id, revision, pr,
                               config) is not None:
                linked.append(execution_id)
    return linked
