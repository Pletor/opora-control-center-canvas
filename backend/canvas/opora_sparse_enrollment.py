"""Sparse context v2 by default: enrollment of accepted cards, automatic for new ones, backfill for old.

Enrolling a card runs the existing explicit v2 preparation (`opora_execution_context.prepare`):
SQL coverage, registry binding and the private key. It never claims, accepts or changes the plan.
Cards that cannot use v2 stay recorded as `unavailable` and keep the documented v1 fallback.
Contract: docs/oporahub-auto-rebase.md ("Sparse kontext v2 ve výchozím stavu")."""
import os

from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_executions import OporaExecutions
from database.repositories.opora_changesets import ChangesetRepository

ENV_SWITCH = "OPORA_SPARSE_CONTEXT_DEFAULT"
NEW_CARD_LIMIT = 16


def default_enabled():
    return os.environ.get(ENV_SWITCH, "1") != "0"


def _rows(db, project, workspace):
    rows = db.execute("SELECT node_id,status,reason,accepted_revision,source,updated_at FROM opora_sparse_enrollment"
                      " WHERE project_id=? AND workspace_id=? ORDER BY node_id", (project, workspace)).fetchall()
    return {row[0]: {"nodeId": row[0], "status": row[1], "reason": row[2], "acceptedRevision": row[3],
                     "source": row[4], "updatedAt": row[5]} for row in rows}


def cards(canvas, project, workspace, revision=None):
    """Card ids (`kind: node`) of an accepted revision that also exist in the working graph."""
    db = canvas.db_for(project)
    repo = ChangesetRepository(db, project, workspace)
    revision = revision or repo.head()
    if revision is None:
        return []
    documents = {item["nodeId"] for item in repo.read(revision)["documents"]}
    graph = canvas.view(project, workspace)["graph"]
    return sorted(node["id"] for node in graph["nodes"] if node.get("kind") == "node" and node["id"] in documents)


def enroll(canvas, project, workspace, node, source):
    """Prepare v2 for one card and remember the outcome; returns the stored row."""
    try:
        result = prepare(OporaExecutions(canvas), {"project": project, "workspace": workspace, "nodeId": node,
                                                   "contextProtocolVersion": 2})
        status, reason, head = "enrolled", result.get("unavailableReason"), result["acceptedHead"]
    except ValueError as error:
        status, reason, head = "unavailable", str(error)[:500], None
    with canvas.lock_for(project):
        db = canvas.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR REPLACE INTO opora_sparse_enrollment VALUES(?,?,?,?,?,?,?,?)",
                       (project, workspace, node, status, reason, head, source, stamp()))
        return _rows(db, project, workspace)[node]


def watermark(canvas, project, workspace):
    """Accepted head at first observation; cards accepted later are new and enroll automatically."""
    with canvas.lock_for(project):
        db = canvas.db_for(project)
        row = db.execute("SELECT accepted_head FROM opora_sparse_watermarks WHERE project_id=? AND workspace_id=?",
                         (project, workspace)).fetchone()
        if row:
            return row[0]
        head = ChangesetRepository(db, project, workspace).head()
        if head is None:
            return None
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO opora_sparse_watermarks VALUES(?,?,?,?)", (project, workspace, head, stamp()))
        return head


def enroll_new(canvas, project, workspace, limit=NEW_CARD_LIMIT):
    mark = watermark(canvas, project, workspace)
    if mark is None:
        return []
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        existing = set(cards(canvas, project, workspace, mark))
        known = _rows(canvas.db_for(project), project, workspace)
        todo = [node for node in cards(canvas, project, workspace) if node not in existing and node not in known]
    return [enroll(canvas, project, workspace, node, "auto") for node in todo[:limit]]


def backfill(canvas, project=None, workspace=None, *, dry_run=False):
    """Enroll every accepted card without a successful enrollment; idempotent, `dry_run` writes nothing."""
    items = []
    for pid in [project] if project else canvas.project_ids():
        with canvas.lock_for(pid):
            rows = canvas.db_for(pid).execute("SELECT workspace_id FROM opora_spec_refs WHERE project_id=?"
                                              " ORDER BY workspace_id", (pid,)).fetchall()
        for (wid,) in rows:
            if workspace and wid != workspace:
                continue
            scope({"project": pid, "workspace": wid})
            with canvas.graph_lock_for(pid), canvas.lock_for(pid):
                known = _rows(canvas.db_for(pid), pid, wid)
                todo = [node for node in cards(canvas, pid, wid) if known.get(node, {}).get("status") != "enrolled"]
            for node in todo:
                if dry_run:
                    items.append({"project": pid, "workspace": wid, "nodeId": node, "status": "would_enroll"})
                else:
                    items.append({"project": pid, "workspace": wid, **enroll(canvas, pid, wid, node, "backfill")})
    return {"dryRun": dry_run, "items": items}


def status(canvas, project, workspace):
    scope({"project": project, "workspace": workspace})
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        known = _rows(canvas.db_for(project), project, workspace)
        listed = cards(canvas, project, workspace)
    return {"defaultEnabled": default_enabled(), "items": [
        {**known.get(node, {"nodeId": node, "status": "not_enrolled"}),
         "defaultContextProtocolVersion": 2 if known.get(node, {}).get("status") == "enrolled" else 1}
        for node in listed]}
