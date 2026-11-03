"""Workflow a jeho neměnné verze: draft → candidate → active → retired; návrat = přepnutí `active`.

Funkce dostávají spojení na registry.sqlite (`CanvasService.db`); zámek drží volající.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from backend.flow.graph_check import FlowInvalid, check_graph
from backend.flow.node_types import NODE_TYPES

KINDS = ("heart", "page_intent", "brain_workflow")


class FlowNotFound(LookupError):
    """Workflow, verze nebo běh neexistuje (HTTP 404)."""


class FlowConflict(RuntimeError):
    """Přechod stavu není z tohoto stavu dovolen (HTTP 409)."""


def _now():
    return datetime.now(UTC).isoformat()


def _version(row):
    return {**dict(row), "graph": json.loads(row["graph"])}


def list_workflows(db, project_id=None):
    rows = db.execute(
        "SELECT w.*, v.id AS active_version_id, v.n AS active_n FROM flow_workflows w "
        "LEFT JOIN flow_workflow_versions v ON v.workflow_id=w.id AND v.status='active' "
        "WHERE (? IS NULL OR w.project_id IS NULL OR w.project_id=?) ORDER BY w.created_at, w.id",
        (project_id, project_id),
    ).fetchall()
    return [dict(row) for row in rows]


def create_workflow(db, kind, name, project_id=None):
    if kind not in KINDS:
        raise FlowInvalid(f"Neznámý kind workflow {kind!r}.")
    if not name or not name.strip():
        raise FlowInvalid("Workflow potřebuje jméno.")
    if project_id is not None and not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
        raise FlowNotFound("Projekt neexistuje.")
    workflow = {"id": uuid.uuid4().hex, "kind": kind, "project_id": project_id, "name": name.strip(),
                "created_at": _now()}
    with db:
        db.execute("INSERT INTO flow_workflows(id,kind,project_id,name,created_at) VALUES(:id,:kind,:project_id,"
                   ":name,:created_at)", workflow)
    return workflow


def get_version(db, version_id):
    row = db.execute("SELECT * FROM flow_workflow_versions WHERE id=?", (version_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Verze workflow neexistuje.")
    return _version(row)


def list_versions(db, workflow_id):
    rows = db.execute("SELECT * FROM flow_workflow_versions WHERE workflow_id=? ORDER BY n", (workflow_id,))
    return [_version(row) for row in rows]


def create_draft(db, workflow_id, graph, parent_version_id=None, registry=NODE_TYPES):
    """Nová neměnná verze s dalším `n`; rodič je zadaná verze, jinak aktivní."""
    if not db.execute("SELECT 1 FROM flow_workflows WHERE id=?", (workflow_id,)).fetchone():
        raise FlowNotFound("Workflow neexistuje.")
    check_graph(graph, registry)
    text = json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with db:
        if parent_version_id is None:
            active = db.execute("SELECT id FROM flow_workflow_versions WHERE workflow_id=? AND status='active'",
                                (workflow_id,)).fetchone()
            parent_version_id = active["id"] if active else None
        elif get_version(db, parent_version_id)["workflow_id"] != workflow_id:
            raise FlowInvalid("Rodičovská verze patří jinému workflow.")
        n = db.execute("SELECT COALESCE(MAX(n),0)+1 FROM flow_workflow_versions WHERE workflow_id=?",
                       (workflow_id,)).fetchone()[0]
        vid = uuid.uuid4().hex
        db.execute(
            "INSERT INTO flow_workflow_versions(id,workflow_id,n,graph,hash,parent_version_id,status,created_at) "
            "VALUES(?,?,?,?,?,?,'draft',?)",
            (vid, workflow_id, n, text, hashlib.sha256(text.encode()).hexdigest(), parent_version_id, _now()),
        )
    return get_version(db, vid)


def set_candidate(db, version_id, eval_run_id=None):
    version = get_version(db, version_id)
    if version["status"] != "draft":
        raise FlowConflict(f"Kandidátem může být jen draft, verze je {version['status']}.")
    with db:
        db.execute("UPDATE flow_workflow_versions SET status='candidate', eval_run_id=? WHERE id=?",
                   (eval_run_id, version_id))
    return get_version(db, version_id)


def _switch_active(db, version):
    with db:
        db.execute("UPDATE flow_workflow_versions SET status='retired' WHERE workflow_id=? AND status='active'",
                   (version["workflow_id"],))
        db.execute("UPDATE flow_workflow_versions SET status='active' WHERE id=?", (version["id"],))
    return get_version(db, version["id"])


def activate(db, version_id):
    """Kandidát (nebo vyřazená verze) se stane jedinou aktivní verzí; dosavadní aktivní jde do `retired`."""
    version = get_version(db, version_id)
    if version["status"] not in ("candidate", "retired"):
        raise FlowConflict(f"Aktivovat jde kandidáta nebo vyřazenou verzi, verze je {version['status']}.")
    return _switch_active(db, version)


def rollback(db, workflow_id):
    """Návrat na předchozí verzi: aktivní bude nejnovější vyřazená verze starší než dnešní aktivní."""
    active = db.execute("SELECT * FROM flow_workflow_versions WHERE workflow_id=? AND status='active'",
                        (workflow_id,)).fetchone()
    if active is None:
        raise FlowConflict("Workflow nemá aktivní verzi.")
    previous = db.execute(
        "SELECT * FROM flow_workflow_versions WHERE workflow_id=? AND status='retired' AND n<? ORDER BY n DESC",
        (workflow_id, active["n"]),
    ).fetchone()
    if previous is None:
        raise FlowConflict("Není předchozí verze, na kterou se vrátit.")
    return _switch_active(db, _version(previous))
