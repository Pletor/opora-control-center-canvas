"""Explicit rollback export; call with all old and new writers stopped."""
import json

from database.repositories.storyboard_revisions import StoryboardRevisions


def export_workspace(canvas, project, workspace, destination):
    """Export into a new directory, retaining SQL history and immutable accepted evidence.

    This does not activate legacy readers or replace the original working files.
    Operators verify the manifest and switch working directories separately.
    """
    if destination.exists():
        raise ValueError("Storyboard rollback destination must be a new directory.")
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        canvas.view(project, workspace)  # Validate the owned project/workspace.
        db = canvas.db_for(project)
        nodes = db.execute("SELECT DISTINCT node_id FROM storyboard_revisions WHERE project_id=? AND workspace_id=? ORDER BY node_id",
                           (project, workspace)).fetchall()
        destination.mkdir(parents=True)
        manifest = [StoryboardRevisions(db, project, workspace, row[0]).export_legacy(destination / f"{row[0]}.json") for row in nodes]
        (destination / "export.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
