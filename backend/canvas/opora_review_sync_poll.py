"""Execution-PR loop step: the server enqueues review jobs (code + security) on its own.

Jobs used to appear only when a review worker claimed (`ReviewTasks.claim` calls `ReviewJobService.sync`).
A worker whose local budget is spent never claims, so a fresh PR head got no job and the card stayed at
`security_review_not_enqueued`. This step runs `sync` for every workspace with an open linked PR, so enqueueing
no longer depends on worker capacity. `sync` is idempotent; claim semantics are unchanged.

Registered in ExecutionPullRequestManager.run_once. Skipped while review jobs are disabled. A failing workspace
is recorded in the error journal and retried on the next pass.
  OPORA_REVIEW_SYNC_SECONDS   interval per project (default 30, 0 = every tick)
"""
import os

from backend.canvas.opora_review_jobs import ReviewJobService


def interval():
    try:
        return max(0, int(os.environ.get("OPORA_REVIEW_SYNC_SECONDS", "30")))
    except ValueError:
        return 30


def poll(manager, project):
    """Returns the ids of the jobs created in this pass."""
    every, now = interval(), manager.clock()
    seen = manager.__dict__.setdefault("review_synced_at", {})
    if project in seen and now - seen[project] < every:
        return []
    seen[project] = now
    jobs = getattr(manager, "review_jobs", None)
    if jobs is None:
        jobs = manager.review_jobs = ReviewJobService(manager.service)
    if not jobs.config()["enabled"]:
        return []
    from backend.app import error_log

    failed = manager.__dict__.setdefault("review_sync_failed", {})  # (projekt, prostor) → text poslední chyby
    created = []
    for workspace in manager._workspaces(project, "SELECT DISTINCT workspace_id FROM opora_execution_pull_requests "
                                                  "WHERE project_id=? AND state='open'"):
        if manager.stop.is_set():
            break
        try:
            created += jobs.sync(project, workspace)
        except Exception as error:  # noqa: BLE001 - jeden prostor nezastaví ostatní, příští průchod to zkusí znovu
            text = f"{type(error).__name__}: {error}"
            # OP-32F3B3.4: log neměl projekt ani páku; jeden záznam na změnu chyby, ne na každý průchod
            if failed.get((project, workspace)) != text:
                failed[(project, workspace)] = text
                error_log.submit("card", "exception", "Zařazení review úloh pro otevřené PR selhalo.", project=project,
                                 workspace=workspace, subject=f"review-sync/{workspace}", cause=text, severity="warn",
                                 lever="Zkontrolovat konfiguraci review jobs projektu; další průchod to zkusí znovu.")
        else:
            if failed.pop((project, workspace), None):
                error_log.resolve(source="card", project=project, subject=f"review-sync/{workspace}")
    return created
