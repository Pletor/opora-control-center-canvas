"""Lifespan-owned loop: when an accepted head advances, auto-rebase stale proposals and enroll new cards.

Each tick handles a bounded number of proposals across projects; a workspace whose head
has not moved since its last complete pass is skipped. Configuration (environment):
  OPORA_AUTO_REBASE=0              disables auto-rebase entirely (explicit rebase stays available)
  OPORA_AUTO_REBASE_WORKER=0       disables only the background loop (tests drive run_once())
  OPORA_AUTO_REBASE_SECONDS        tick interval (default 5)
  OPORA_AUTO_REBASE_BATCH          proposals per tick (default 16, max 256)
  OPORA_SPARSE_CONTEXT_DEFAULT=0   disables automatic sparse-context enrollment of new cards"""
import logging
import os
import threading

from backend.canvas import opora_auto_rebase as auto
from backend.canvas import opora_sparse_enrollment as sparse

LOGGER = logging.getLogger(__name__)


def interval():
    try:
        return max(0.5, float(os.environ.get("OPORA_AUTO_REBASE_SECONDS", "5")))
    except ValueError:
        return 5.0


class AutoRebaseManager:
    def __init__(self, service, *, tick=None):
        self.service, self.tick = service, tick
        self.rebase = auto.AutoRebase(service)
        self.stop, self.thread, self.seen = threading.Event(), None, {}

    def start(self):
        if (not auto.enabled() or os.environ.get("OPORA_AUTO_REBASE_WORKER", "1") == "0"
                or self.thread or self.stop.is_set()):
            return
        self.thread = threading.Thread(target=self._loop, name="opora-auto-rebase", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _loop(self):
        while not self.stop.wait(self.tick or interval()):
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("Auto-rebase loop unavailable; retrying safely.")

    def _workspaces(self, project):
        with self.service.lock_for(project):
            rows = self.service.db_for(project).execute(
                "SELECT workspace_id,accepted_id FROM opora_spec_refs WHERE project_id=? ORDER BY workspace_id",
                (project,)).fetchall()
        return [(row[0], row[1]) for row in rows]

    def run_once(self):
        """One bounded pass; returns the per-workspace summaries that did work."""
        budget, results = auto.batch_limit(), []
        for project in self.service.project_ids():
            for workspace, head in self._workspaces(project):
                if self.stop.is_set() or budget <= 0:
                    return results
                if self.seen.get((project, workspace)) == head:
                    continue
                try:
                    summary = self.rebase.run(project, workspace, limit=budget)
                    if sparse.default_enabled():
                        summary["enrolled"] = sparse.enroll_new(self.service, project, workspace)
                except ValueError:
                    LOGGER.warning("Auto-rebase skipped %s/%s.", project, workspace)
                    continue
                touched = sum(len(summary[key]) for key in ("rebased", "redundant", "conflicts", "skipped"))
                budget -= touched
                if not summary["remaining"]:
                    self.seen[(project, workspace)] = head
                if touched or summary.get("enrolled"):
                    results.append({"project": project, "workspace": workspace, **summary})
        return results
