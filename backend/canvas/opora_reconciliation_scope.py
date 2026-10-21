"""Server-only enrollment identity and historical subscription scope fences."""
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_review_policy_identity import pinned_repository
from backend.canvas.opora_review_scope import configuration, context
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_review_evidence import ReviewEvidenceRepository


def read_context(service, project, workspace):
    """Archived workspaces retain readable history without regaining writable authority."""
    scope({"project": project, "workspace": workspace})
    with service.registry_lock:
        archived = service.db.execute("SELECT 1 FROM archived_workspaces WHERE project_id=? AND id=?",
                                      (project, workspace)).fetchone()
    if not archived:
        return context(service, project, workspace)
    revisions = ChangesetRepository(service.db_for(project), project, workspace)
    head = revisions.head()
    if head:
        revisions.read(head)
    return {"acceptedHead": head, "available": False, "unavailableReason": "Workspace is archived.",
            "repository": None, "config": None}


def candidate(service, project, workspace, evidence_id):
    current = context(service, project, workspace)
    if not current["available"]:
        raise ValueError(current["unavailableReason"])
    snapshot = ReviewEvidenceRepository(service.db_for(project), project, workspace).read(evidence_id)
    repository = pinned_repository(snapshot, current)
    if snapshot["acceptedRevision"] != current["acceptedHead"]:
        raise ValueError("Enrollment requires evidence for the current accepted revision.")
    return current, {"acceptedRevision": current["acceptedHead"], "identityEvidenceId": evidence_id,
                     "repository": repository, "pr": {key: snapshot["pr"][key] for key in ("id", "number", "headRepoId")},
                     "enrolledHeadSha": snapshot["pr"]["headSha"], "configuration": current["config"], "intervalSeconds": 300}


def historical_context(service, project, workspace, binding):
    if (binding["project"], binding["workspace"]) != (project, workspace):
        raise ValueError("Subscription scope changed.")
    if service.view(project, workspace)["readOnly"]:
        raise ValueError("Subscription workspace is read-only or archived.")
    if configuration(service, project) != binding["configuration"]:
        raise ValueError("Subscription configuration changed; human attention required.")
    revisions = ChangesetRepository(service.db_for(project), project, workspace)
    revisions.read(binding["acceptedRevision"])
    return {"acceptedHead": revisions.head()}
