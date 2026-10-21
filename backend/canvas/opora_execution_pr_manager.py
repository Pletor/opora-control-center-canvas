"""Lifespan-owned sibling of the reconciliation scheduler that closes the execution loop.

Each tick (bounded batch of projects): apply merge/close write-back from reconciliation
observations, retry pending auto-enrollments and, at a configurable interval, discover
PRs by trailers. Network never holds Canvas or SQLite locks; GitHub rate limits impose a
global cooldown. Configuration (environment):
  OPORA_EXECUTION_PR_WORKER=0             disables the loop entirely
  OPORA_EXECUTION_PR_DISCOVERY_SECONDS    discovery interval per project (default 300, 0 = off)"""
import logging
import os
import threading
import time
from contextlib import contextmanager

from backend.canvas.opora_execution_pr_closure import close_loop
from backend.canvas.opora_execution_pr_discovery import discover
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.integrations.github_merge_transport import GitHubMergeError
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

LOGGER = logging.getLogger(__name__)
BATCH = 16


class Stopped(RuntimeError):
    """The loop is shutting down; no further database access."""


def discovery_interval():
    try:
        return max(0, int(os.environ.get("OPORA_EXECUTION_PR_DISCOVERY_SECONDS", "300")))
    except ValueError:
        return 300


class ExecutionPullRequestManager:
    def __init__(self, service, links=None, *, clock=time.time, tick=5):
        self.service, self.clock, self.tick = service, clock, tick
        self.links = links or ExecutionPullRequestLinks(service, clock=clock)
        self.stop, self.gate, self.thread = threading.Event(), threading.RLock(), None
        self.cursor, self.cooldown_until, self.discovered_at = 0, 0, {}
        self.links.guard = self._guard

    @contextmanager
    def _guard(self):
        with self.gate:
            if self.stop.is_set():
                raise Stopped
            yield

    def start(self):
        if os.environ.get("OPORA_EXECUTION_PR_WORKER", "1") == "0" or self.thread or self.stop.is_set():
            return
        self.thread = threading.Thread(target=self._loop, name="execution-pr-loop", daemon=True)
        self.thread.start()

    def _loop(self):
        # First tick waits too: startup never races the app into a GitHub read.
        while not self.stop.wait(self.tick):
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("Execution PR loop unavailable; retrying safely.")

    def close(self):
        self.stop.set()
        with self.gate:
            pass
        if self.thread:
            self.thread.join(timeout=1)

    def _workspaces(self, project, sql):
        with self._guard(), self.service.graph_lock_for(project), self.service.lock_for(project):
            return [row[0] for row in self.service.db_for(project).execute(sql, (project,)).fetchall()]

    def _close(self, project):
        for workspace in self._workspaces(project, "SELECT DISTINCT workspace_id FROM opora_execution_pull_requests "
                                                   "WHERE project_id=? AND state IN ('open','closed')"):
            with self.links.transaction(project, workspace) as repo:
                close_loop(repo.db, project, workspace)

    def _enroll(self, project):
        for workspace in self._workspaces(project, "SELECT DISTINCT workspace_id FROM opora_execution_pull_requests "
                                                   "WHERE project_id=? AND enrollment='pending'"):
            with self.links.transaction(project, workspace) as repo:
                due = ExecutionPullRequests(repo.db, project, workspace).pending_enrollment(self.clock(), limit=5)
            for row in due:
                if self.stop.is_set() or self.clock() < self.cooldown_until:
                    return
                self.links.enroll(project, workspace, row["execution_id"])
                self._cooldown()

    def _discover(self, project):
        interval, now = discovery_interval(), self.clock()
        if not interval or now < self.cooldown_until or now - self.discovered_at.get(project, -interval) < interval:
            return
        self.discovered_at[project] = now
        try:
            discover(self.service, self.links, project)
        except GitHubMergeError as error:
            self.cooldown_until = max(self.cooldown_until, now + (error.retry_after or 0))
        finally:
            self._cooldown()

    def _cooldown(self):
        wait = getattr(self.links.reader, "retry_after", 0) or 0
        if wait:
            self.cooldown_until = max(self.cooldown_until, self.clock() + wait)

    def run_once(self):
        with self.gate:
            projects = [] if self.stop.is_set() else self.service.project_ids()
        batch = projects[self.cursor:self.cursor + BATCH]
        self.cursor = 0 if self.cursor + BATCH >= len(projects) else self.cursor + BATCH
        for project in batch:
            if self.stop.is_set():
                return
            try:
                self._close(project)
                self._enroll(project)
                self._discover(project)
            except Stopped:
                return
            except (ValueError, GitHubMergeError):
                LOGGER.warning("Execution PR loop skipped project %s.", project)
