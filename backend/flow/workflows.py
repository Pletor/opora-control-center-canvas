"""Workflow a jeho neměnné verze: draft → candidate → active → retired; návrat = přepnutí `active`.

Funkce dostávají spojení na registry.sqlite (`CanvasService.db`); zámek drží volající.
Záměr stránky (`kind = page_intent`, `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §2–§3) patří stránce
(`owner_ref = opora:page:<nodeId>`), má vlastní katalog uzlů a kandidáta aktivuje jen člověk přes `approve`.
"""

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime

from backend.flow.graph_check import FlowInvalid, check_graph
from backend.flow.node_types import catalog
from backend.flow.run_log import append

KINDS = ("heart", "page_intent", "brain_workflow")
PAGE_OWNER = re.compile(r"opora:page:\S+")


class FlowNotFound(LookupError):
    """Workflow, verze nebo běh neexistuje (HTTP 404)."""


class FlowConflict(RuntimeError):
    """Přechod stavu není z tohoto stavu dovolen (HTTP 409); `code` je strojový důvod (`approval_required` …)."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _now():
    return datetime.now(UTC).isoformat()


def _version(row):
    return {**dict(row), "graph": json.loads(row["graph"])}


def list_workflows(db, project_id=None, kind=None, owner_ref=None):
    rows = db.execute(
        "SELECT w.*, v.id AS active_version_id, v.n AS active_n FROM flow_workflows w "
        "LEFT JOIN flow_workflow_versions v ON v.workflow_id=w.id AND v.status='active' "
        "WHERE (? IS NULL OR w.project_id IS NULL OR w.project_id=?) AND (? IS NULL OR w.kind=?) "
        "AND (? IS NULL OR w.owner_ref=?) ORDER BY w.created_at, w.id",
        (project_id, project_id, kind, kind, owner_ref, owner_ref),
    ).fetchall()
    return [dict(row) for row in rows]


def create_workflow(db, kind, name, project_id=None, owner_ref=None):
    """`page_intent` patří stránce projektu (`owner_ref = opora:page:<nodeId>`), `heart` nemá vlastníka."""
    if kind not in KINDS:
        raise FlowInvalid(f"Neznámý kind workflow {kind!r}.")
    if not name or not name.strip():
        raise FlowInvalid("Workflow potřebuje jméno.")
    if kind == "page_intent" and (project_id is None or not PAGE_OWNER.fullmatch(owner_ref or "")):
        raise FlowInvalid("Záměr stránky potřebuje project_id a owner_ref ve tvaru opora:page:<nodeId>.")
    if kind == "heart" and owner_ref is not None:
        raise FlowInvalid("Workflow srdce nemá owner_ref.")
    if project_id is not None and not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
        raise FlowNotFound("Projekt neexistuje.")
    workflow = {"id": uuid.uuid4().hex, "kind": kind, "project_id": project_id, "name": name.strip(),
                "created_at": _now(), "owner_ref": owner_ref}
    try:
        with db:
            db.execute("INSERT INTO flow_workflows(id,kind,project_id,name,created_at,owner_ref) VALUES(:id,:kind,"
                       ":project_id,:name,:created_at,:owner_ref)", workflow)
    except sqlite3.IntegrityError as error:
        raise FlowConflict(f"Vlastník {owner_ref} už workflow {kind} má.", "owner_taken") from error
    return workflow


def workflow_kind(db, workflow_id):
    row = db.execute("SELECT kind FROM flow_workflows WHERE id=?", (workflow_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Workflow neexistuje.")
    return row["kind"]


def get_version(db, version_id):
    row = db.execute("SELECT * FROM flow_workflow_versions WHERE id=?", (version_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Verze workflow neexistuje.")
    return _version(row)


def list_versions(db, workflow_id):
    rows = db.execute("SELECT * FROM flow_workflow_versions WHERE workflow_id=? ORDER BY n", (workflow_id,))
    return [_version(row) for row in rows]


def create_draft(db, workflow_id, graph, parent_version_id=None, registry=None):
    """Nová neměnná verze s dalším `n`; rodič je zadaná verze, jinak aktivní. Graf ověří katalog druhu workflow."""
    kind = workflow_kind(db, workflow_id)
    check_graph(graph, registry or catalog(kind), kind)
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
    if workflow_kind(db, version["workflow_id"]) == "page_intent":
        raise FlowConflict("Záměr stránky aktivuje jen člověk schválením (approve).", "approval_required")
    if version["status"] not in ("candidate", "retired"):
        raise FlowConflict(f"Aktivovat jde kandidáta nebo vyřazenou verzi, verze je {version['status']}.")
    return _switch_active(db, version)


def _intent_candidate(db, version_id):
    version = get_version(db, version_id)
    if workflow_kind(db, version["workflow_id"]) != "page_intent":
        raise FlowConflict("Schválení a zamítnutí verze je jen pro záměr stránky (page_intent).")
    if version["status"] != "candidate":
        raise FlowConflict(f"Schválit nebo zamítnout jde jen kandidáta, verze je {version['status']}.")
    return version


def _decision(version, author, reason=None):
    payload = {"workflow_id": version["workflow_id"], "version_id": version["id"], "n": version["n"],
               "author": author}
    return payload if reason is None else {**payload, "reason": reason}


def approve(db, version_id, author, page_digest=None):
    """Člověk schválí kandidáta záměru: stane se aktivní verzí, do logu jde `version.approved` (plátno 2) s otiskem
    stránky v okamžiku schválení (`pageDigest`, `page_intents.page_digest`); podle něj se pozná zastaralý záměr."""
    version = _intent_candidate(db, version_id)
    payload = {**_decision(version, author), "pageDigest": page_digest}
    append(db, None, None, "version.approved", payload, canvas=2)  # commit až se `_switch_active`
    return _switch_active(db, version)


def reject(db, version_id, reason, author):
    """Člověk zamítne kandidáta záměru: verze jde do `retired`, důvod do logu `version.rejected` (plátno 2)."""
    if not reason or not reason.strip():
        raise FlowInvalid("Zamítnutí potřebuje důvod.")
    version = _intent_candidate(db, version_id)
    with db:
        db.execute("UPDATE flow_workflow_versions SET status='retired' WHERE id=?", (version_id,))
        append(db, None, None, "version.rejected", _decision(version, author, reason.strip()), canvas=2)
    return get_version(db, version_id)


def rollback(db, workflow_id):
    """Návrat na předchozí verzi: aktivní bude nejnovější vyřazená verze starší než dnešní aktivní.
    Zamítnutý kandidát (`version.rejected` v logu) aktivní nikdy nebyl, návrat ho přeskočí."""
    active = db.execute("SELECT * FROM flow_workflow_versions WHERE workflow_id=? AND status='active'",
                        (workflow_id,)).fetchone()
    if active is None:
        raise FlowConflict("Workflow nemá aktivní verzi.")
    previous = db.execute(
        "SELECT * FROM flow_workflow_versions v WHERE workflow_id=? AND status='retired' AND n<? AND NOT EXISTS("
        "SELECT 1 FROM flow_log_events e WHERE e.type='version.rejected' "
        "AND json_extract(e.payload,'$.version_id')=v.id) ORDER BY n DESC",
        (workflow_id, active["n"]),
    ).fetchone()
    if previous is None:
        raise FlowConflict("Není předchozí verze, na kterou se vrátit.")
    return _switch_active(db, _version(previous))
