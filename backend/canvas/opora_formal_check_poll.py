"""Execution-PR loop step: read `formal/tlc` on every open linked PR head and record it.

Registered in ExecutionPullRequestManager.run_once. Network never holds Canvas or
SQLite locks; a rate-limit or forbidden answer pauses the whole loop like other reads.
  OPORA_FORMAL_CHECK_SECONDS   interval per project (default 300, 0 = off)
"""
import os
import weakref

from backend.canvas.opora_formal_checks import known, record_check
from backend.integrations.github_formal_check_reader import GitHubFormalCheckReader
from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader
from backend.integrations.github_review_transport import GitHubReadError
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

RATE_LIMIT_PAUSE = 60
_polled = weakref.WeakKeyDictionary()
_readers = weakref.WeakKeyDictionary()


def interval():
    try:
        return max(0, int(os.environ.get("OPORA_FORMAL_CHECK_SECONDS", "300")))
    except ValueError:
        return 300


def register_reader(manager, reader):
    """Tests and integrations inject a reader for one manager."""
    _readers[manager] = reader


def poll(manager, project):
    every, now = interval(), manager.clock()
    seen = _polled.setdefault(manager, {})
    if not every or now < manager.cooldown_until or now - seen.get(project, -every) < every:
        return 0
    reader = _readers.get(manager)
    if reader is None:
        if not isinstance(manager.links.reader, GitHubPullRequestLinkReader):
            return 0  # An injected offline link reader means no live GitHub reads here either.
        reader = _readers.setdefault(manager, GitHubFormalCheckReader())
    seen[project] = now
    stored = 0
    for workspace in manager._workspaces(project, "SELECT DISTINCT workspace_id FROM opora_execution_pull_requests "
                                                   "WHERE project_id=? AND state='open'"):
        with manager.links.transaction(project, workspace) as repo:
            rows = [row for row in ExecutionPullRequests(repo.db, project, workspace).unresolved(limit=20)
                    if row["state"] == "open"]
        for row in rows:
            if manager.stop.is_set():
                return stored
            try:
                checks = [check for check in reader.checks(row["repository"], row["head_sha"])
                          if check["status"] == "completed"]
                with manager.links.transaction(project, workspace) as repo:
                    checks = [check for check in checks if not known(repo.db, project, workspace,
                                                                     row["execution_id"], check)]
                notes = {check["id"]: reader.annotations(row["repository"], check["id"])
                         for check in checks if check["conclusion"] != "success"}
            except GitHubReadError as error:
                if error.status in (403, 429):
                    manager.cooldown_until = max(manager.cooldown_until, manager.clock() + RATE_LIMIT_PAUSE)
                    return stored
                continue
            for check in checks:
                with manager.links.transaction(project, workspace) as repo:
                    if record_check(repo.db, project, workspace, check, repository=row["repository"],
                                    number=row["number"], annotations=notes.get(check["id"]),
                                    via="execution-pr-loop"):
                        stored += 1
    return stored
