"""Fronta úkolů mozku (docs/brain-gate.md §6, H1b): zápis úkolů, `next` a `report` pro pracovníky brány.

Úkoly píše člověk nebo srdce projektu (H2a, `created_by = "heart"`). Pracovník si přes bránu řekne o další (`next`), úkol mu zůstane, dokud ho
neohlásí (`report`): všechny kontroly zelené = `done`, červená = zpět do `ready`, druhá červená = `failed`.
Kontroly se jen zapisují do `check_runs` u nahlášeného sha; aplikace sama nic nespouští a nevolá model.
Úkol relace s prošlým nebo zneplatněným tokenem se vrátí do `ready` při nejbližším `next` kohokoli; pracovník ho
může vrátit sám (`release` s důvodem). Zelené hlášení musí nést sha, které ve zdrojovém repu prostoru existuje.
Změny stavu (vznik, přidělení, done, failed, zrušení, vrácení) vydají událost `gate.task`.
Sprinty (docs/navrhy/2026-10-31-sprinty-a-uspornost.md §2): úkol s `body.sprint` je kontrolním bodem, když za ním
ve frontě už žádný otevřený úkol téhož sprintu není (odvozeno při čtení, nic se neukládá); úkol bez sprintu je
kontrolním bodem vždy. Mimo kontrolní bod smí pracovník hlásit kontroly `deferred` (pak `done`), kontrolní bod ne.
"""
import sqlite3
import subprocess
import uuid

from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_payloads import (
    empty_body,
    release_payload,
    report_payload,
    status_filter,
    task_payload,
)
from backend.canvas.check_runs import CheckRuns
from backend.canvas.opora_events import emit_event
from backend.canvas.opora_process_sync import ProcessSync
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories.heart_tasks import OPEN, HeartTaskStore

PLAN_LIMIT = 20
MAX_ATTEMPTS = 2
OUTPUT_LIMIT = 1500
GIT_TIMEOUT = 10
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


def _emit(db, project, task, actor, **extra):
    emit_event(db, project_id=project, workspace_id=task["workspaceId"], kind="gate.task", node_id=task["nodeId"],
               actor=actor, data={"taskId": task["taskId"], "status": task["status"], **extra})


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


def sprint_of(task):
    """`body.sprint` úkolu (`{id, goal?, milestone[]?}`), nebo None u úkolu bez sprintu."""
    sprint = task["body"].get("sprint") if isinstance(task.get("body"), dict) else None
    return sprint if isinstance(sprint, dict) and sprint.get("id") else None


def _queued(task):
    return task.get("order") or 0, task["seq"]


def is_checkpoint(task, mates):
    """True, když za úkolem ve frontě (`order`, `seq`) není žádný otevřený (`ready`/`assigned`) úkol téhož sprintu.
    `mates` jsou úkoly prostoru (stačí téhož sprintu); úkol bez sprintu je kontrolním bodem vždy."""
    sprint = sprint_of(task)
    if sprint is None:
        return True
    return not any(other["taskId"] != task["taskId"] and other["status"] in OPEN and _queued(other) > _queued(task)
                   and (sprint_of(other) or {}).get("id") == sprint["id"] for other in mates)


def sprint_summary(sprint_id, mates):
    """`{id, goal, milestone, done, total}` sprintu z úkolů prostoru: goal a milestone z prvního úkolu (v pořadí
    fronty), který je nese; počty přes úkoly sprintu kromě zrušených."""
    own = sorted((task for task in mates if (sprint_of(task) or {}).get("id") == sprint_id), key=_queued)
    goal = next((sprint_of(task)["goal"] for task in own if (sprint_of(task).get("goal") or "").strip()), "")
    milestone = next((list(sprint_of(task)["milestone"]) for task in own if sprint_of(task).get("milestone")), [])
    live = [task for task in own if task["status"] != "cancelled"]
    return {"id": sprint_id, "goal": goal, "milestone": milestone,
            "done": sum(task["status"] == "done" for task in live), "total": len(live)}


def for_worker(task, mates=()):
    """Úkol v pevném tvaru, jak ho dostane pracovník (`next`, `state.myTask`): k polím úkolu `checkpoint` a `sprint`
    (`{id, goal, milestone, done, total}`, u úkolu bez sprintu null) odvozené z `mates`, úkolů téhož sprintu."""
    sprint = sprint_of(task)
    return {**{key: task[value] for key, value in (("id", "taskId"), ("title", "title"), ("nodeId", "nodeId"),
                                                   ("status", "status"), ("attempts", "attempts"), ("body", "body"))},
            "checkpoint": is_checkpoint(task, mates), "sprint": sprint_summary(sprint["id"], mates) if sprint else None}


def worker_task(store, task):
    """`for_worker` s úkoly sprintu načtenými ze skladu (jen u úkolu se sprintem)."""
    sprint = sprint_of(task)
    return for_worker(task, store.in_sprints(task["workspaceId"], sprint["id"]) if sprint else ())


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
            shown = worker_task(store, task) if task is not None else None
    if shown is not None:
        return {"task": shown}
    # Přehled karet bere vlastní zámky (graf, pak projekt), proto až po uvolnění zámku fronty.
    return {"task": None, "plan": open_cards(service, project, workspace)}


def _detail(check):
    output = check.get("output", "")
    return (check["name"] + (": " + output[:OUTPUT_LIMIT] if output else "")).replace("\0", "")


def _held(store, task_id, session, hint):
    """Úkol držený touto relací, jinak 404 `task_not_found` / 409 `task_not_assigned`."""
    task = store.get(task_id)
    if task is None:
        raise _missing_task()
    if task["status"] != "assigned" or task["sessionId"] != session["id"]:
        raise GateError(409, "task_not_assigned", "Úkol není přidělený této relaci.", hint)
    return task


def source_root(service, project, workspace):
    """Kořen zdrojového repa prostoru, nebo None (žádný zdroj, nedostupný, mimo hranici)."""
    try:
        return WorkspaceSources(service).root(project, workspace)
    except (ValueError, KeyError, OSError, sqlite3.Error):
        return None


def commit_exists(root, sha):
    """True / False podle `git cat-file -e <sha>^{commit}`; None, když kořen není repo gitu nebo git nejde spustit."""
    try:
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT)
        if inside.returncode != 0:
            return None
        found = subprocess.run(["git", "-C", str(root), "cat-file", "-e", sha + "^{commit}"], capture_output=True,
                               stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return found.returncode == 0


REPORT_HELD = "Hlaste jen úkol, který vám vrátil next; o další požádejte přes next."


def _check_sha(service, session, task_id, sha):
    """Zelené hlášení: sha musí být commit ve zdrojovém repu prostoru. Git běží mimo zámek projektu."""
    project = session["project_id"]
    with service.reading(project):
        task = _held(HeartTaskStore(service.db_for(project), project), task_id, session, REPORT_HELD)
    root = source_root(service, project, task["workspaceId"])
    if root is not None and commit_exists(root, sha) is False:
        raise GateError(422, "sha_unknown", f"Commit {sha} ve zdrojovém repu pracovního prostoru neexistuje.",
                        "Commitni práci a nahlas sha z `git rev-parse HEAD`.")


def _refuse_deferred_at_checkpoint(store, task):
    """Kontrolní bod sprintu (i úkol bez sprintu) musí hlásit skutečné kontroly: `deferred` → 422."""
    sprint = sprint_of(task)
    if is_checkpoint(task, store.in_sprints(task["workspaceId"], sprint["id"]) if sprint else ()):
        raise GateError(422, "checkpoint_needs_checks", "Úkol je kontrolním bodem sprintu; kontroly nejde odložit.",
                        'Spusťte kontroly milníku sprintu a pošlete je jako green nebo red, ne deferred.')


def report(service, session, body, now=None):
    """Obsluha `report`: kontroly do `check_runs` u sha a výsledek úkolu → `{task: {id, status, attempts}}`.

    Kontroly `deferred` se nezapisují a o výsledku nerozhodují; smí je nést jen úkol, který není kontrolním bodem.
    Hlášení jen z odložených kontrol je `done` a sha se ověří jako u zeleného."""
    task_id, sha, summary, checks = report_payload(body)
    project = session["project_id"]
    deferred = any(check["status"] == "deferred" for check in checks)
    checks_run = [check for check in checks if check["status"] != "deferred"]
    if all(check["status"] == "green" for check in checks_run):
        _check_sha(service, session, task_id, sha)
    with service.lock_for(project):
        db = service.db_for(project)
        task = _held(HeartTaskStore(db, project), task_id, session, REPORT_HELD)
        if deferred:
            _refuse_deferred_at_checkpoint(HeartTaskStore(db, project), task)
        runs = CheckRuns(service)
        scope = (project, task["workspaceId"], task["nodeId"] or task_id)
        for check in checks_run:  # každý zápis má vlastní transakci (append-only check_runs)
            runs.record(scope, {"status": check["status"], "sha": sha, "detail": _detail(check)})
        red = any(check["status"] == "red" for check in checks_run)
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


def release(service, session, body, now=None):
    """Obsluha `release`: držený úkol zpět do `ready` bez relace (`attempts` beze změny), důvod jde do `gate.task`."""
    task_id, reason = release_payload(body)
    project = session["project_id"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = HeartTaskStore(db, project)
            _held(store, task_id, session, "Vrátit jde jen úkol, který držíte (vrátil vám ho next).")
            store.release(task_id, session["id"], tokens.stamp(now))
            task = store.get(task_id)
            _emit(db, project, task, _agent(session), reason=reason)
    return {"task": {"id": task_id, "status": task["status"], "attempts": task["attempts"]}}
