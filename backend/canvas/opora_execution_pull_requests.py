"""Execution -> PR link authority (OporaHub phase 1B, docs/oporahub-executions.md).

An agent holding the active lease of an execution (token + epoch, same fencing as
heartbeat/results) or a human session links exactly one PR. Linking is idempotent by
requestId, the same PR is a no-op and a different PR is a conflict. A successful link
auto-enrolls durable reconciliation; GitHub reads happen outside every lock."""
import re
import time
from contextlib import contextmanager, nullcontext

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_events import emit_event, refresh
from backend.canvas.opora_execution_pr_closure import close_loop
from backend.canvas.opora_execution_pr_enrollment import apply_enrollment, configured, fail
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_hub_store import content_id
from backend.integrations.github_merge_transport import GitHubMergeError
from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests, public

LINK = {"requestId", "repository", "number", "headRef", "headSha"}
CREDENTIALS = {"token", "epoch"}
REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")


class LinkMissing(LookupError):
    """No PR is linked to this execution (HTTP 404)."""


def aliased(payload):
    """agent-office sends projectId/workspaceId; the rest of the execution API uses project/workspace."""
    if not isinstance(payload, dict) or not {"projectId", "workspaceId"} & set(payload):
        return payload
    if {"project", "workspace"} & set(payload):
        raise ValueError("Use either project/workspace or projectId/workspaceId.")
    result = {key: value for key, value in payload.items() if key not in ("projectId", "workspaceId")}
    result["project"], result["workspace"] = payload.get("projectId"), payload.get("workspaceId")
    return result


def validate_link(payload, actor):
    keys = LINK | CREDENTIALS if actor == "agent" or (isinstance(payload, dict) and CREDENTIALS & set(payload)) else LINK
    project, workspace = validate(payload, keys)
    repository = payload["repository"]
    if (not isinstance(repository, str) or len(repository) > 255 or ".." in repository
            or REPOSITORY.fullmatch(repository) is None):
        raise ValueError("Invalid repository; expected owner/name.")
    if type(payload["number"]) is not int or not 1 <= payload["number"] <= 2147483647:
        raise ValueError("Invalid pull request number.")
    ref = payload["headRef"]
    if not isinstance(ref, str) or not 1 <= len(ref) <= 255 or any(ord(char) < 32 for char in ref):
        raise ValueError("Invalid head ref.")
    if not isinstance(payload["headSha"], str) or re.fullmatch(r"[a-f0-9]{40}", payload["headSha"]) is None:
        raise ValueError("Invalid head SHA.")
    return project, workspace


class ExecutionPullRequestLinks:
    def __init__(self, service, reader=None, *, clock=time.time):
        self.service, self.clock = service, clock
        self.executions = OporaExecutions(service)
        self.reader = reader or GitHubPullRequestLinkReader()
        # The background loop installs a shutdown guard so late network results never touch a closed DB.
        self.guard = nullcontext

    @contextmanager
    def transaction(self, project, workspace):
        with self.guard(), self.executions.transaction(project, workspace) as repo:
            yield repo

    def authorize(self, repo, record):
        """Lease holder: a running execution with a valid lease, or one whose own result was reported.

        Office links the PR after the worker submitted its result, often after the lease was
        released, so the execution's own token + epoch remain the credential. An execution with
        neither an active lease nor a reported result (released/expired/revoked) is rejected."""
        if record["state"] == "running":
            try:
                self.executions.active(repo, record)
                return
            except ValueError:
                pass
        if record["state"] == "reported" or repo.receipts(record["executionId"]):
            return
        raise ValueError("Execution has no active lease and no reported result; it is no longer authoritative.")

    def link(self, execution_id, payload, actor, *, source=None):
        payload = aliased(payload)
        project, workspace = validate_link(payload, actor)
        repository, number = payload["repository"].casefold(), payload["number"]
        digest = content_id({"executionId": execution_id, "repository": repository, "number": number,
                             "headRef": payload["headRef"], "headSha": payload["headSha"]})
        with self.transaction(project, workspace) as repo:
            links = ExecutionPullRequests(repo.db, project, workspace)
            record = repo.read(execution_id)
            if "token" in payload:
                self.executions.authenticate(record, payload["token"], payload["epoch"])
            prior = links.replay(payload["requestId"])
            if prior is not None:
                if prior != (execution_id, digest):
                    raise ValueError("Request identity was already used for a different PR link.")
                row = links.read(execution_id)
            else:
                if actor == "agent":
                    self.authorize(repo, record)
                row = links.read(execution_id)
                if row is not None and (row["repository"], row["number"]) != (repository, number):
                    raise ValueError("Execution already has a different linked pull request.")
                if row is not None and (row["head_sha"], row["head_ref"]) != (payload["headSha"], payload["headRef"]):
                    # Same PR, new pushed head: update the link, never a conflict.
                    row = links.update(execution_id, head_sha=payload["headSha"], head_ref=payload["headRef"],
                                       updated_at=stamp())
                    refresh(repo.db, project, workspace, row["node_id"], actor)
                if row is None:
                    ChangesetRepository(repo.db, project, workspace).read(record["acceptedRevision"])
                    config = configured(self.service, project)
                    if config is not None and config["repository"] != repository:
                        raise ValueError("Pull request repository differs from the project repository.")
                    now = stamp()
                    row = links.insert({
                        "execution_id": execution_id, "node_id": record["nodeId"],
                        "accepted_revision": record["acceptedRevision"], "repository": repository, "number": number,
                        "head_ref": payload["headRef"], "head_sha": payload["headSha"], "state": "open",
                        "binding_id": None, "enrollment": "pending" if config else "unavailable",
                        "enrollment_error": None if config else "github-not-configured", "enrollment_retry_at": None,
                        "enrollment_failures": 0, "merge_sha": None, "merged_at": None, "awaiting_human_close": 0,
                        "attention": None, "source": source or actor, "linked_by": actor,
                        "created_at": now, "updated_at": now})
                    emit_event(repo.db, project_id=project, workspace_id=workspace, kind="pr.linked",
                               node_id=row["node_id"], execution_id=execution_id, pr_number=number, actor=actor,
                               data={"repository": repository, "headSha": row["head_sha"], "headRef": row["head_ref"]})
                links.remember(payload["requestId"], execution_id, digest)
        if row["enrollment"] == "pending" and row["enrollment_retry_at"] is None:
            self.enroll(project, workspace, execution_id)
        return self.read(project, workspace, execution_id)

    def enroll(self, project, workspace, execution_id, observed=None):
        """Read PR identity outside locks, then bind it in one transaction. Failures retry with backoff."""
        error = None
        if observed is None:
            with self.transaction(project, workspace) as repo:
                row = ExecutionPullRequests(repo.db, project, workspace).read(execution_id)
            if row is None or row["enrollment"] != "pending":
                return row
            try:
                observed = self.reader.pull_request(row["repository"], row["number"])
            except (GitHubMergeError, ValueError, KeyError, TypeError) as failure:
                error = failure if isinstance(failure, GitHubMergeError) else GitHubMergeError("github-malformed")
        with self.transaction(project, workspace) as repo:
            links = ExecutionPullRequests(repo.db, project, workspace)
            row = links.read(execution_id)
            if row is None or row["enrollment"] != "pending":
                return row
            if error is not None:
                return fail(links, row, error.code, self.clock(), retry=not error.action_required)
            row = apply_enrollment(self.service, links, row, observed, self.clock())
            close_loop(repo.db, project, workspace)
            if row is not None:
                refresh(repo.db, project, workspace, row["node_id"])
            return links.read(execution_id)

    def read(self, project, workspace, execution_id):
        validate({"project": project, "workspace": workspace}, set())
        with self.transaction(project, workspace) as repo:
            links = ExecutionPullRequests(repo.db, project, workspace)
            row = links.read(execution_id)
            if row is None:
                raise LinkMissing("No pull request is linked to this execution.")
            events = links.events(execution_id)
        return {**self._decorate(project, workspace, [public(row)])[0], "events": events}

    def list_execution_pull_requests(self, project_id, workspace_id):
        """Link rows with PR state for consumers such as the agent-state endpoint.

        A pure snapshot read (no BEGIN IMMEDIATE): agent-state composes it under its own project
        locks and promises a read-only document, so this must never open a write transaction."""
        from database.repositories.opora_execution_pull_requests import list_execution_pull_requests
        validate({"project": project_id, "workspace": workspace_id}, set())
        with self.guard(), self.service.reading(project_id):
            rows = list_execution_pull_requests(self.service.db_for(project_id), project_id, workspace_id)
        return self._decorate(project_id, workspace_id, rows)

    def _decorate(self, project, workspace, rows):
        """A human-confirmed card no longer awaits closing; the marker is derived, not rewritten."""
        if not any(row["awaitingHumanClose"] for row in rows):
            return rows
        from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
        nodes = DesktopV3State(self.service).read(project, workspace)["state"]["nodes"]
        return [{**row, "awaitingHumanClose": row["awaitingHumanClose"]
                 and not nodes.get(row["cardId"], {}).get("done", {}).get("confirmed", False)} for row in rows]


def list_execution_pull_requests(service, project_id, workspace_id):
    return ExecutionPullRequestLinks(service).list_execution_pull_requests(project_id, workspace_id)
