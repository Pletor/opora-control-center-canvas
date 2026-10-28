"""Explicit SQL promotion for accepted local drafts; legacy rows stay historical."""
from backend.canvas.architecture_graph import split
from backend.canvas.graph import encode
from backend.canvas.opora_graph_execution import require_accepted_graph
from backend.canvas.payload_errors import NextStep
from backend.canvas.workspace_graph_storage import save_authoritative
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_context_events import enroll as enroll_journal
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority


def draft_authoritative_raw(canvas, project):
    db = canvas.db_for(project)
    row = WorkspaceGraphAuthority(db, project, "draft").read()
    if row is not None:
        return encode(row["graph"])
    # Explicit promotion always journals enrollment first. This immutable event
    # distinguishes a deleted authority from an accepted, never-promoted v1 draft.
    promoted = db.execute(
        "SELECT 1 FROM opora_context_events WHERE project_id=? "
        "AND source_table='workspace_graph_authority' "
        "AND (json_extract(after_json,'$.workspace_id')='draft' "
        "OR json_extract(before_json,'$.workspace_id')='draft') LIMIT 1", (project,)
    ).fetchone()
    if promoted:
        raise ValueError("Promoted draft graph authority is missing; legacy fallback is forbidden.")
    return None


def save_sql_draft(canvas, project, workspace, content, architecture=None, previous=None,
                   changed=False, actor="system", kept=None, *, commit=False):
    if workspace != "draft" or draft_authoritative_raw(canvas, project) is None:
        return False
    return save_authoritative(canvas, project, workspace, content, architecture, previous,
                              changed, actor, kept, commit=commit)


def promote_sql_draft(canvas, project, workspace, accepted_head):
    """Caller owns graph/project locks and transaction; no Git/file enrollment."""
    db = canvas.db_for(project)
    if not db.in_transaction:
        raise RuntimeError("Draft SQL promotion requires caller transaction.")
    accepted = ChangesetRepository(db, project, workspace)
    if accepted_head is None or accepted.head() != accepted_head or not accepted.read(accepted_head).get("graphManifestId"):
        raise NextStep(
            "Převzetí karty potřebuje přijatý graf plánu; přijatá revize "
            + (str(accepted_head) if accepted_head else "zatím není") + " nemá manifest grafu plánu (graphManifestId; je jen zadání karet).",
            code="graph_acceptance_required",
            hint="Proveď akci propose_graph z agent-state (POST /api/oporahub/graph-proposals s prázdným plánem "
                 "{nodes: [], edges: []} nad acceptedHead; když už návrh grafu čeká, tento krok vynech), pak akci "
                 "accept návrhu (POST /api/oporahub/graph-proposals/{id}/accept, tělo = project, workspace a "
                 "preconditions akce); potom claim znovu. Skriptem: opora_hub.py act --action-id ID.")
    authority = WorkspaceGraphAuthority(db, project, workspace)
    row = authority.read()
    local = project == "draft" or canvas.project_hub.source_info(canvas.row("projects", project))["sourceKind"] in ("local", "empty")
    if not local and row is None:
        raise ValueError("Git/file workspace graphs require existing SQL authority.")
    if local and workspace != "draft":
        raise ValueError("Local SQL promotion requires workspace draft.")
    graph = canvas.view(project, workspace)["graph"]
    require_accepted_graph(canvas, project, workspace, accepted_head, graph)
    if row is None:
        enroll_journal(db, project)
        row = authority.enroll(split(graph)[1])
    return row
