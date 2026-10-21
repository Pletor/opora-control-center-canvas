"""Workspace-wide GitHub history, deliberately without invented card/PR joins."""
from backend.canvas.opora_review_status import evaluate
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs
from database.repositories.opora_review_evidence import ReviewEvidenceRepository


def tracking(db, project, workspace, accepted):
    repo = ReconciliationRepository(db, project, workspace)
    jobs = ReconciliationJobs(db, project, workspace)
    bindings = repo.bindings(101)
    evidence = ReviewEvidenceRepository(db, project, workspace).list(101)
    items = []
    for binding in bindings[:100]:
        control = repo.latest_control(binding["id"])
        job = jobs.public(binding["id"]) or {}
        observation_id = job.get("lastObservationId")
        observation = repo.read("observation", observation_id) if observation_id else None
        snapshot = next((value for value in evidence[:100]
                         if value["acceptedRevision"] == binding["acceptedRevision"]
                         and value.get("repository", {}).get("id") == binding["repository"]["id"]
                         and value.get("pr", {}).get("id") == binding["pr"]["id"]), None)
        verdict = evaluate(snapshot, accepted) if snapshot else None
        items.append({"bindingId": binding["id"], "acceptedRevision": binding["acceptedRevision"],
                      "matchesCurrentRevision": binding["acceptedRevision"] == accepted,
                      "enabled": bool(control and control["enabled"]), "jobStatus": job.get("state"),
                      "lastObservationId": observation_id,
                      "reviewStatus": verdict["codeReview"]["status"] if verdict else None,
                      "observedPrState": observation["data"]["pr"]["state"] if observation else None})
    reviews = []
    for snapshot in evidence[:100]:
        verdict = evaluate(snapshot, accepted)
        reviews.append({"evidenceId": snapshot["id"], "acceptedRevision": snapshot["acceptedRevision"],
                        "matchesCurrentRevision": snapshot["acceptedRevision"] == accepted,
                        "codeReview": verdict["codeReview"]["status"], "planReview": verdict["planReview"]["status"],
                        "freshness": verdict["freshness"]["status"]})
    return {"scope": "workspace", "limit": 100, "truncated": len(bindings) > 100 or len(evidence) > 100,
            "items": items, "reviews": reviews}
