"""Sparse read projections keep historical facts separate from current job health."""
import os

from backend.canvas.authority import can_act
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_reconciliation_scope import read_context
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs


def item(repo, jobs, binding, current):
    job = jobs.public(binding["id"])
    observation = repo.read("observation", job["lastObservationId"]) if job.get("lastObservationId") else None
    attempt = jobs.latest_attempt(binding["id"])
    return {"binding": binding, "control": repo.latest_control(binding["id"]), "job": job,
            "latestAttempt": attempt, "lastSuccessfulObservation": observation,
            "revisionRelation": {"boundAcceptedRevision": binding["acceptedRevision"],
                                 "currentAcceptedRevision": current["acceptedHead"],
                                 "matchesCurrentAcceptedRevision": binding["acceptedRevision"] == current["acceptedHead"]}}


def listing(service, project, workspace, actor):
    with service.graph_lock_for(project), service.lock_for(project):
        current = read_context(service, project, workspace)
        db = service.db_for(project)
        repo, jobs = ReconciliationRepository(db, project, workspace), ReconciliationJobs(db, project, workspace)
        return {"project": project, "workspace": workspace, "currentAcceptedHead": current["acceptedHead"],
                "canConfigure": can_act(actor) and current["available"],
                "canPause": can_act(actor),
                "automaticWorkerEnabled": os.environ.get("OPORA_RECONCILIATION_WORKER", "1") != "0",
                "automaticWorkerUnavailableReason": ("Automatic reconciliation worker is disabled by server configuration."
                    if os.environ.get("OPORA_RECONCILIATION_WORKER", "1") == "0" else None),
                "unavailableReason": current["unavailableReason"] or (None if can_act(actor) else "Human UI session required."),
                "serverNow": stamp(), "items": [item(repo, jobs, b, current) for b in repo.bindings()]}
