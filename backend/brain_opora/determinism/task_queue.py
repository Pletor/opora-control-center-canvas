"""Fronta úkolů mozku (docs/brain-gate.md §6, H1b): zápis úkolů, `next` a `report` pro pracovníky brány.

Úkoly píše člověk nebo srdce projektu (H2a, `created_by = "heart"`). Pracovník si přes bránu řekne o další (`next`), úkol mu zůstane, dokud ho
neohlásí (`report`): všechny kontroly zelené = `done`, červená = zpět do `ready`, druhá červená = `failed`.
Kontroly se jen zapisují do `check_runs` u nahlášeného sha; aplikace sama nic nespouští a nevolá model.
Úkol relace s prošlým nebo zneplatněným tokenem se vrátí do `ready` při nejbližším `next` kohokoli.
Změny stavu (vznik, přidělení, done, failed, zrušení) vydají událost `gate.task`.
"""
import sqlite3
import uuid

from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_payloads import (
    empty_body,
    report_payload,
    status_filter,
    task_payload,
)
from backend.canvas.check_runs import CheckRuns
from backend.canvas.opora_events import emit_event
from backend.canvas.opora_process_sync import ProcessSync
from database.repositories.heart_tasks import HeartTaskStore

PLAN_LIMIT = 20
MAX_ATTEMPTS = 2
OUTPUT_LIMIT = 1500
HUMAN = {"kind": "human", "name": None}
HEART = {"kind": "agent", "name": "heart"}
WRITERS = ("human", "heart")


def _missing_project():
    return GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")


def _check_scope(service, project, workspace):
    if not service.project_exists(project):
        raise _missing_project()
    if workspace not in ("draft", "main") and not any(row["id"] == workspace for row in service.workspaces(project)):
        raise GateError(404, "workspace_not_found", "Pracovní prostor v projektu neexistuje.",
                        "Použijte main, draft nebo ID pracovního prostoru projektu.")


def _missing_task():
    return GateError(404, "task_not_found", "Úkol v projektu neexistuje.", "ID úkolu vrací next nebo GET /api/brain/tasks.")


def _emit(db, project, task, actor):
    emit_event(db, project_id=project, workspace_id=task["workspaceId"], kind="gate.task", node_id=task["nodeId"],
               actor=actor, data={"taskId": task["taskId"], "status": task["status"]})


def _agent(session):
    return {"kind": "agent", "name": session["worker_name"]}


def writer_actor(by):
    """Původce události podle pisatele úkolu: člověk, nebo srdce projektu."""
    if by not in WRITERS:
        raise ValueError("Úkol píše jen člověk nebo srdce.")
    return HUMAN if by == "human" else HEART


def create(service, payload, created_by="human", now=None):
    """`POST /api/brain/tasks` → nový úkol ve stavu `ready`; `order` řadí frontu (nižší dřív)."""
    actor = writer_actor(created_by)
    project, workspace, node, title, body, order = task_payload(payload)
    _check_scope(service, project, workspace)
    task_id, at = "ht_" + uuid.uuid4().hex, tokens.stamp(now)
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = HeartTaskStore(db, project)
            store.insert(task_id, workspace, node, title, body, created_by, at, order)
            task = store.get(task_id)
            _emit(db, project, task, actor)
    return task


def list_tasks(service, project, workspace, status=None):
    """`GET /api/brain/tasks` → `{tasks}` pracovního prostoru od nejstaršího; čtení je volné."""
    status = status_filter(status)
    _check_scope(service, project, workspace or "")
    with service.reading(project):
        return {"tasks": HeartTaskStore(service.db_for(project), project).list(workspace, status)}


def cancel(service, project, task_id, now=None, by="human"):
    """`POST /api/brain/tasks/{id}/cancel` → zrušený úkol; hotový nebo zrušený je 409 `task_closed`."""
    actor = writer_actor(by)
    if not service.project_exists(project):
        raise _missing_project()
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = HeartTaskStore(db, project)
            if store.get(task_id) is None:
                raise _missing_task()
            if not store.cancel(task_id, tokens.stamp(now)):
                raise GateError(409, "task_closed", "Úkol už je uzavřený (done, failed nebo cancelled).",
                                "Zrušit jde jen úkol ve stavu ready nebo assigned.")
            task = store.get(task_id)
            _emit(db, project, task, actor)
    return task


def for_worker(task):
    """Úkol v pevném tvaru, jak ho dostane pracovník (`next`, `state.myTask`)."""
    return {key: task[value] for key, value in (("id", "taskId"), ("title", "title"), ("nodeId", "nodeId"),
                                                ("status", "status"), ("attempts", "attempts"), ("body", "body"))}


def open_cards(service, project, workspace):
    """Otevřené karty `{id, name, stage}` (nejvýš 20) z přehledu procesu, z něhož skládá stav pro agenty i etapy.

    Plán je jen nápověda pro prázdnou frontu; když přehled nejde přečíst, je prázdný a `next` přesto odpoví.
    """
    try:
        items = ProcessSync(service).read(project, workspace, limit=None)["items"]
    except (ValueError, KeyError, OSError, sqlite3.Error):
        return []
    cards = [{"id": item["nodeId"], "name": item["name"], "stage": item["status"]}
             for item in items if item["status"] != "closed"]
    return cards[:PLAN_LIMIT]


def next_task(service, session, body, now=None):
    """Obsluha `next`: držený úkol znovu, jinak nejstarší `ready`; prázdná fronta = `{task: null, plan}`."""
    empty_body(body)
    project, workspace, at = session["project_id"], session["workspace_id"], tokens.stamp(now)
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = HeartTaskStore(db, project)
            store.reclaim(at)
            task = store.held_by(session["id"])
            if task is None:
                ready = store.oldest_ready(workspace)
                if ready is not None and store.assign(ready["taskId"], session["id"], at):
                    task = store.get(ready["taskId"])
                    _emit(db, project, task, _agent(session))
    if task is not None:
        return {"task": for_worker(task)}
    # Přehled karet bere vlastní zámky (graf, pak projekt), proto až po uvolnění zámku fronty.
    return {"task": None, "plan": open_cards(service, project, workspace)}


def _detail(check):
    output = check.get("output", "")
    return (check["name"] + (": " + output[:OUTPUT_LIMIT] if output else "")).replace("\0", "")


def report(service, session, body, now=None):
    """Obsluha `report`: kontroly do `check_runs` u sha a výsledek úkolu → `{task: {id, status, attempts}}`."""
    task_id, sha, summary, checks = report_payload(body)
    project = session["project_id"]
    with service.lock_for(project):
        db = service.db_for(project)
        task = HeartTaskStore(db, project).get(task_id)
        if task is None:
            raise _missing_task()
        if task["status"] != "assigned" or task["sessionId"] != session["id"]:
            raise GateError(409, "task_not_assigned", "Úkol není přidělený této relaci.",
                            "Hlaste jen úkol, který vám vrátil next; o další požádejte přes next.")
        runs = CheckRuns(service)
        scope = (project, task["workspaceId"], task["nodeId"] or task_id)
        for check in checks:  # každý zápis má vlastní transakci (append-only check_runs)
            runs.record(scope, {"status": check["status"], "sha": sha, "detail": _detail(check)})
        red = any(check["status"] == "red" for check in checks)
        attempts = task["attempts"] + (1 if red else 0)
        status = ("failed" if attempts >= MAX_ATTEMPTS else "ready") if red else "done"
        outcome = {"sha": sha, "summary": summary, "checks": checks}
        with db:
            store = HeartTaskStore(db, project)
            store.finish(task_id, session["id"], status, attempts, outcome, tokens.stamp(now))
            task = store.get(task_id)
            if status != "ready":
                _emit(db, project, task, _agent(session))
    return {"task": {"id": task_id, "status": task["status"], "attempts": task["attempts"]}}
