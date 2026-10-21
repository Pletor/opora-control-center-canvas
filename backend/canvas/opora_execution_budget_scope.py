"""Budget scope is accepted Canvas authority and does not require a GitHub repository."""

from backend.canvas.opora_change_validation import scope
from database.repositories.opora_changesets import ChangesetRepository


def current(service, project, workspace, node):
    scope({"project": project, "workspace": workspace})
    if project != "draft":
        service.row("projects", project)
    db = service.db_for(project)
    revisions = ChangesetRepository(db, project, workspace)
    accepted = revisions.head()
    accepted_record = revisions.read(accepted) if accepted else None
    with service.registry_lock:
        archived = service.db.execute(
            "SELECT 1 FROM archived_workspaces WHERE project_id=? AND id=?", (project, workspace)
        ).fetchone()
    if archived:
        return {
            "acceptedHead": accepted,
            "available": False,
            "unavailableReason": "Workspace is archived.",
        }
    view = service.view(project, workspace)
    target = next((item for item in view["graph"]["nodes"] if item["id"] == node), None)
    reason = (
        "Workspace is read-only."
        if view["readOnly"]
        else "An accepted revision is required."
        if not accepted
        else "An executable accepted target card is required."
        if (
            not target
            or target["kind"] not in ("node", "sector")
            or node not in {item["nodeId"] for item in accepted_record["documents"]}
        )
        else None
    )
    return {"acceptedHead": accepted, "available": not reason, "unavailableReason": reason}
