"""Scoped native preimages for operation intents; no alternate fragment authority."""
import hashlib
import json

from backend.canvas.opora_changesets import OporaChangesets
from backend.editor.brief_vault.brief_vault import BriefVault

TABLES = (
    "brief_fragment_revisions", "brief_fragment_details", "brief_fragment_feedback",
    "brief_gate_proposals", "brief_gate_proposal_rejections", "brief_lessons", "brief_lesson_events",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def snapshot(service, project, workspace):
    """Locks belong to the caller. Include full text/details, graph/state and accepted specifications."""
    view = service.view(project, workspace)
    db = service.db_for(project)
    rows = {table: sorted((dict(row) for row in db.execute(
        f"SELECT * FROM {table} WHERE project_id=? AND workspace_id=?", (project, workspace))), key=canonical)
        for table in TABLES}
    return {"tables": rows, "graph": view["graph"], "digest": view["digest"], "readOnly": view["readOnly"],
            "state": BriefVault(service).state.current(project, workspace),
            "specifications": OporaChangesets(service).context(project, workspace)}


def result_fragments(value):
    """Locate native fragment projections anywhere in the finite handler result."""
    found = []
    if isinstance(value, dict):
        if {"id", "revision", "kind", "chars", "scopeNodeId"} <= value.keys():
            found.append(value)
        for item in value.values():
            found.extend(result_fragments(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(result_fragments(item))
    return found


def verify_result(service, project, workspace, result):
    """Verify native immutable revisions, including deleted/historical fragments, from SQL authority."""
    from backend.canvas.payload_errors import NextStep
    from backend.editor.brief_vault.brief_vault_model import public
    db = service.db_for(project)
    for item in result_fragments(result):
        row = db.execute("SELECT * FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? "
                         "AND fragment_id=? AND revision=?", (project, workspace, item["id"], item["revision"])).fetchone()
        actual = public(row, with_text="text" in item) if row else {}
        if actual != item or not row:
            raise NextStep("Native fragment result differs from its stored revision.", code="operation_incomplete",
                           hint="Read the existing operation and pinned fragment before retrying.")
    from backend.editor.brief_vault.operation_result_readback import verify_details
    verify_details(service, project, workspace, result)
