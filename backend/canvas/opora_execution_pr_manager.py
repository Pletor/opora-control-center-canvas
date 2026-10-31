"""Lifespan-owned sibling of the reconciliation scheduler that closes the execution loop.

Each tick (bounded batch of projects): apply merge/close write-back from reconciliation
observations, retry pending auto-enrollments and, at a configurable interval, discover
PRs by trailers, and close every merged card whose definition of done is met (opora_card_auto_close,
deterministic, no model). Network never holds Canvas or SQLite locks; GitHub rate limits impose a
global cooldown. Configuration (environment):
  OPORA_EXECUTION_PR_WORKER=0             disables the loop entirely
  OPORA_EXECUTION_PR_DISCOVERY_SECONDS    discovery interval per project (default 300, 0 = off)
  OPORA_REVIEW_SYNC_SECONDS               server-side review job enqueue interval per project (default 30, 0 = every tick)
  OPORA_CARD_AUTO_CLOSE_SECONDS           card close re-evaluation interval per project (default 30, 0 = every tick)"""
import logging
import os
import threading
import time
from contextlib import contextmanager

from backend.canvas.opora_card_auto_close import sweep as close_cards
from backend.canvas.opora_execution_pr_closure import close_loop
from backend.canvas.opora_execution_pr_discovery import discover
from backend.canvas.opora_execution_pr_enrollment import AUTH, HEALABLE
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_formal_check_poll import poll as poll_formal_checks
from backend.canvas.opora_review_sync_poll import poll as sync_review_jobs
from backend.integrations.github_merge_transport import GitHubMergeError
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

LOGGER = logging.getLogger(__name__)
BATCH = 16


class Stopped(RuntimeError):
    """The loop is shutting down; no further database access."""


def auto_close_interval():
    try:
        return max(0, int(os.environ.get("OPORA_CARD_AUTO_CLOSE_SECONDS", "30")))
    except ValueError:
        return 30


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
        self.cursor, self.cooldown_until, self.discovered_at, self.healed = 0, 0, {}, set()
        self.closed_at = {}
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

    def _workspaces(self, project, sql, *params):
        with self._guard(), self.service.graph_lock_for(project), self.service.lock_for(project):
            return [row[0] for row in self.service.db_for(project).execute(sql, (project, *params)).fetchall()]

    def _close(self, project):
        for workspace in self._workspaces(project, "SELECT DISTINCT workspace_id FROM opora_execution_pull_requests "
                                                   "WHERE project_id=? AND state IN ('open','closed')"):
            with self.links.transaction(project, workspace) as repo:
                close_loop(repo.db, project, workspace)

    def _heal(self, project):
        """Once per process: links whose enrollment failed or backed off on a token problem retry now.

        The fix for such a failure is a new token and a restart, so the restart retries them; without this
        an already merged PR would never be observed (or only after the backoff of every 401 before the
        restart) and its successor card would stay blocked."""
        if project in self.healed:
            return
        # A failed link on any token problem, and a pending one backing off on a rejected or missing token
        # (a passing outage keeps its own backoff).
        due = ("binding_id IS NULL AND ((enrollment='failed' AND enrollment_error IN ({})) "
               "OR (enrollment='pending' AND enrollment_error IN ({})))").format(
            ",".join("?" * len(HEALABLE)), ",".join("?" * len(AUTH)))
        for workspace in self._workspaces(project, "SELECT DISTINCT workspace_id FROM opora_execution_pull_requests "
                                                   f"WHERE project_id=? AND {due}", *HEALABLE, *AUTH):
            with self.links.transaction(project, workspace) as repo:
                repo.db.execute("UPDATE opora_execution_pull_requests SET enrollment='pending',enrollment_retry_at=NULL,"
                                f"enrollment_failures=0 WHERE project_id=? AND workspace_id=? AND {due}",
                                (project, workspace, *HEALABLE, *AUTH))
        self.healed.add(project)

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

    def _close_cards(self, project):
        """Deterministic card close after merge and plan write-back; the first tick after a restart runs it."""
        now = self.clock()
        if project in self.closed_at and now - self.closed_at[project] < auto_close_interval():
            return
        self.closed_at[project] = now
        with self._guard():
            close_cards(self.service, project)

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
                self._close_cards(project)
                self._heal(project)
                self._enroll(project)
                self._discover(project)
                poll_formal_checks(self, project)
                sync_review_jobs(self, project)
            except Stopped:
                return
            except (ValueError, GitHubMergeError):
                LOGGER.warning("Execution PR loop skipped project %s.", project)
