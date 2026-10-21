"""SQLite authority adapters; unenrolled Git workspaces retain their file storage."""
from backend.canvas.graph import encode
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority


def authority_record(db, project, workspace):
    row = WorkspaceGraphAuthority(db, project, workspace).read()
    if row is None:
        accepted = ChangesetRepository(db, project, workspace)
        head = accepted.head()
        if head is not None and accepted.read(head).get("graphManifestId") is not None:
            raise ValueError("Accepted workspace graph authority is missing; file fallback is forbidden.")
    return row


def authoritative_raw(service, project, workspace):
    row = authority_record(service.db_for(project), project, workspace)
    return None if row is None else encode(row["graph"])


def save_authoritative(service, project, workspace, content, architecture, previous,
                       changed, actor, kept, *, commit):
    """Return False only for unenrolled scopes; integrity failures must propagate."""
    with service.lock_for(project):
        db = service.db_for(project)
        store = WorkspaceGraphAuthority(db, project, workspace)
        row = authority_record(db, project, workspace)
        if row is None:
            return False
        if not commit and not db.in_transaction:
            raise RuntimeError("Transactional graph write requires an existing transaction.")
        try:
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            row = authority_record(db, project, workspace)
            if row is None:
                raise ValueError("Workspace graph enrollment disappeared during write.")
            if changed:
                service.architecture.write(db, project, architecture, previous,
                                           actor, workspace, kept)
            store.write(content, row["revision"])
            if commit:
                db.commit()
        except Exception:
            if commit:
                db.rollback()
            raise
        return True


def refuse_authority_restore(db):
    """Historical architecture backups cannot discard immutable OporaHub history."""
    from backend.canvas.opora_reconciliation_restore import refuse_reconciliation_restore
    from backend.canvas.opora_review_policy_restore import refuse_policy_restore
    refuse_policy_restore(db)
    refuse_reconciliation_restore(db)
    if db.execute("SELECT 1 FROM workspace_graph_authority LIMIT 1").fetchone():
        raise ValueError("Architecture backup restore is unavailable after workspace graph enrollment.")
    if db.execute("SELECT 1 FROM opora_execution_epochs LIMIT 1").fetchone():
        raise ValueError("Architecture backup restore is unavailable after execution enrollment.")
    if db.execute("SELECT 1 FROM opora_spec_refs LIMIT 1").fetchone():
        raise ValueError("Architecture backup restore is unavailable after accepted plan history.")
    if (db.execute("SELECT 1 FROM opora_graph_proposals LIMIT 1").fetchone()
            or db.execute("SELECT 1 FROM opora_graph_manifests LIMIT 1").fetchone()):
        raise ValueError("Architecture backup restore is unavailable after graph proposal history.")
