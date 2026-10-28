"""Snímek projektu pro srdce (docs/brain-heart.md §3): deterministický text bez modelu, s pevným stropem znaků.

`collect` přečte fakta (identita projektu, stránky plánu, fronta úkolů, čekající lístky, poslední kontroly),
`render` z nich bez dalšího čtení složí text. Stejná fakta = stejný text; nic tu nezávisí na čase ani náhodě.
Každá část má vlastní strop počtu řádků a celý text se nakonec ořízne na `LIMIT` znaků.
"""
import json
import sqlite3

from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_queue import open_cards
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_tasks import HeartTaskStore

LIMIT = 12_000  # zhruba 4k tokenů
PAGES = 20
TASKS = 10
TICKETS = 10
CHECKS = 10
TEXT = 160
STATUSES = ("ready", "assigned", "done", "failed", "cancelled")
CUT = "\n… (snímek zkrácen)"


def _short(value, limit=TEXT):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _identity(service, project):
    try:
        identity = service.folder(project).read()
    except (ValueError, OSError):
        return project, ""
    settings = identity.get("settings") if isinstance(identity.get("settings"), dict) else {}
    return identity.get("name") or project, settings.get("goal") or ""


def _pages(service, project, workspace):
    """Stránky plánu `{id, name, path, goal, feel}` z grafu plátna; nečitelný graf = žádné stránky."""
    try:
        nodes = service.view(project, workspace)["graph"]["nodes"]
    except (ValueError, KeyError, OSError, sqlite3.Error):
        return []
    pages = []
    for node in nodes:
        site = node.get("site") if isinstance(node.get("site"), dict) else {}
        if site.get("kind") == "page":
            pages.append({"id": node["id"], "name": node.get("name") or node["id"], "path": site.get("path") or "",
                          "goal": site.get("goal") or "", "feel": site.get("feel") or ""})
    return pages


def collect(service, project, workspace):
    """Fakta snímku jednoho pracovního prostoru. Neexistující projekt je 404 `project_not_found`."""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    name, goal = _identity(service, project)
    pages, cards = _pages(service, project, workspace), open_cards(service, project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        tasks = HeartTaskStore(db, project).list(workspace)
        tickets = GateTicketStore(db, project).queued(workspace, TICKETS)
        checks = db.execute("SELECT scope_id, sha, status FROM check_runs WHERE project_id=? AND workspace_id=?"
                            " ORDER BY recorded_at DESC, scope_id LIMIT ?", (project, workspace, CHECKS)).fetchall()
    return {"project": project, "name": name, "workspace": workspace, "goal": goal, "pages": pages, "cards": cards,
            "tasks": tasks, "tickets": tickets, "checks": [tuple(row) for row in checks]}


def _intent(facts):
    if facts["goal"].strip():
        return _short(facts["goal"], 400)
    home = next((page for page in facts["pages"] if page["path"].rstrip("/") == ""), None)
    if home and (home["goal"] or home["feel"]):
        return _short(" · ".join(part for part in (home["goal"], home["feel"]) if part), 400)
    return "—"


def _plan(facts):
    stages = {card["id"]: card["stage"] for card in facts["cards"]}
    if facts["pages"]:
        rows = [f"- {_short(page['name'], 80)} · {page['path'] or '—'} · {stages.get(page['id'], 'closed')}"
                + (f" · cíl: {_short(page['goal'], 120)}" if page["goal"] else "")
                for page in facts["pages"][:PAGES]]
    else:
        rows = [f"- {_short(card['name'], 80)} · {card['id']} · {card['stage']}" for card in facts["cards"][:PAGES]]
    return rows or ["- (prázdný plán)"]


def _queue(facts):
    tasks = facts["tasks"]
    counts = {status: sum(task["status"] == status for task in tasks) for status in STATUSES}
    holders = sorted({task["sessionId"] for task in tasks if task["status"] == "assigned" and task["sessionId"]})
    head = (f"ready {counts['ready']} · assigned {counts['assigned']}"
            + (f" ({', '.join(holders)})" if holders else "")
            + f" · done {counts['done']} · failed {counts['failed']}")
    last = sorted(tasks, key=lambda task: task["seq"], reverse=True)[:TASKS]
    return [head, *(f"- [{task['status']}] {_short(task['title'], 100)} ({task['taskId']})" for task in last)]


def render(facts, limit=LIMIT):
    """Text snímku podle §3; delší než `limit` znaků se ořízne a označí."""
    lines = [f"PROJEKT {_short(facts['name'], 120)} ({facts['project']}) · workspace {facts['workspace']}",
             f"ZÁMĚR: {_intent(facts)}", "PLÁN:", *_plan(facts), "FRONTA ÚKOLŮ: " + _queue(facts)[0],
             *_queue(facts)[1:], "LÍSTKY ČEKAJÍCÍ:"]
    tickets = facts["tickets"][:TICKETS]
    lines += [f"- {t['ticketId']} {t['kind']} {_short(json.dumps(t['body'], ensure_ascii=False, sort_keys=True), 200)}" for t in tickets] or ["- žádné"]
    lines.append("POSLEDNÍ KONTROLY:")
    lines += [f"- {scope} {sha[:12]} {status}" for scope, sha, status in facts["checks"][:CHECKS]] or ["- žádné"]
    text = "\n".join(lines)
    return text if len(text) <= limit else text[: limit - len(CUT)] + CUT


def snapshot(service, project, workspace, limit=LIMIT):
    """Snímek jako text: `render(collect(...))`."""
    return render(collect(service, project, workspace), limit)
