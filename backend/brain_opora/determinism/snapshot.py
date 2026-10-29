"""Snímek projektu pro srdce (docs/brain-heart.md §3): deterministický text bez modelu, s pevným stropem znaků.

`collect` přečte fakta (identita projektu, zprávy člověka, pravidla a rozhodnutí z paměti Desktop v3, stránky plánu,
fronta úkolů, čekající lístky, poslední kontroly, deník dávek; okolí srdce §3a; skripty dílny §3b), `render` z nich bez dalšího čtení
složí text. Stejná fakta = stejný text; nic tu nezávisí na čase ani náhodě.
Každá část má vlastní strop počtu řádků a celý text se nakonec ořízne na `LIMIT` znaků.
`view` složí ze stejných faktů kompaktní JSON pro druh brány `state` (docs/brain-control-api.md §2).
"""
import json
import sqlite3

from backend.brain_opora.determinism import brain_files
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_queue import for_worker, open_cards
from database.repositories.gate_tickets import GateTicketStore
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.heart_tasks import HeartTaskStore

LIMIT = 12_000  # zhruba 4k tokenů
PAGES = 20
TASKS = 10
TICKETS = 10
CHECKS = 10
TEXT = 160
STATUSES = ("ready", "assigned", "done", "failed", "cancelled")
QUEUE = ("ready", "assigned", "done", "failed")
RULES = 20
MESSAGES = 5
MESSAGE_TEXT = 400
DECISIONS = 10
JOURNAL = 5
SCRIPTS = 15
UNREADABLE = (ValueError, KeyError, TypeError, AttributeError, OSError, sqlite3.Error)
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


def _memory(service, project, workspace):
    """Pravidla s rozsahem projekt a rozhodnutí z paměti Desktop v3; nečitelná paměť = nic."""
    store = getattr(service, "desktop_v3_state", None) or DesktopV3State(service)
    try:
        state = store.read(project, workspace)["state"]
        rules = [rule for rule in state.get("rules") or [] if isinstance(rule, dict) and rule.get("scope") == "project"]
        decisions = [item for item in state.get("decisions") or [] if isinstance(item, dict)]
    except UNREADABLE:
        return [], []
    return rules, decisions


def _brain(service, project, workspace):
    """Zprávy člověka tohoto pracovního prostoru, deník dávek a skripty dílny ze složky `brain/`; nečitelné = nic."""
    try:
        brain = brain_files.brain_dir(service, project)
    except UNREADABLE:
        return [], [], []
    return (brain_files.messages(brain, workspace, MESSAGES), brain_files.journal(brain, JOURNAL),
            brain_files.scripts(brain, SCRIPTS))


def collect(service, project, workspace):
    """Fakta snímku jednoho pracovního prostoru. Neexistující projekt je 404 `project_not_found`."""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    name, goal = _identity(service, project)
    rules, decisions = _memory(service, project, workspace)
    messages, journal, scripts = _brain(service, project, workspace)
    pages, cards = _pages(service, project, workspace), open_cards(service, project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        tasks = HeartTaskStore(db, project).list(workspace)
        tickets = GateTicketStore(db, project).queued(workspace, TICKETS)
        checks = db.execute("SELECT scope_id, sha, status FROM check_runs WHERE project_id=? AND workspace_id=?"
                            " ORDER BY recorded_at DESC, scope_id LIMIT ?", (project, workspace, CHECKS)).fetchall()
    return {"project": project, "name": name, "workspace": workspace, "goal": goal, "pages": pages, "cards": cards,
            "tasks": tasks, "tickets": tickets, "checks": [tuple(row) for row in checks], "messages": messages,
            "rules": rules, "decisions": decisions, "journal": journal, "scripts": scripts}


def _intent(facts):
    """Záměr z cíle projektu, jinak z domovské stránky; žádný = prázdný text."""
    if facts["goal"].strip():
        return _short(facts["goal"], 400)
    home = next((page for page in facts["pages"] if page["path"].rstrip("/") == ""), None)
    if home and (home["goal"] or home["feel"]):
        return _short(" · ".join(part for part in (home["goal"], home["feel"]) if part), 400)
    return ""


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
    return [head, *(f"- [{task['status']}] {_short(task['title'], 100)} ({task['taskId']})" + _held_since(task)
                    for task in last)]


def _held_since(task):
    """U drženého úkolu kdo a od kdy (`updatedAt` nastaví přidělení); čas jako údaj, ne délka, ať je snímek stálý."""
    if task["status"] != "assigned":
        return ""
    return f" · drží {task.get('sessionId') or '?'} od {task.get('updatedAt') or '?'}"


def _approved(rule):
    return rule.get("by", "human") != "agent"


def _project_rules(facts):
    """Pravidla aplikace: schválená, pak návrhy agenta; obojí v uloženém pořadí."""
    rules = facts.get("rules") or []
    return [rule for rule in rules if _approved(rule)] + [rule for rule in rules if not _approved(rule)]


def _decisions(facts):
    """Připnutá rozhodnutí první, pak od nejnovějšího (`createdAt`, při shodě `id`)."""
    newest = sorted(facts.get("decisions") or [], key=lambda item: (str(item.get("createdAt") or ""),
                                                                     str(item.get("id") or "")), reverse=True)
    return [item for item in newest if item.get("pinned") is True] + [item for item in newest
                                                                      if item.get("pinned") is not True]


def _section(head, rows):
    return [head, *(rows or ["- žádné"])]


def _memory_lines(facts):
    messages = [f"- {entry.get('at') or '—'} {_short(entry.get('text'), MESSAGE_TEXT)}"
                for entry in (facts.get("messages") or [])[-MESSAGES:]]
    rules = [f"- {_short(rule.get('text'), 300)}" + ("" if _approved(rule) else " (návrh)")
             for rule in _project_rules(facts)[:RULES]]
    decisions = [f"- {'[připnuto] ' if item.get('pinned') is True else ''}{_short(item.get('text'), 300)}"
                 + (f" · karta {item['nodeId']}" if item.get("nodeId") else "")
                 + (f" · {item['path']}" if item.get("path") else "") for item in _decisions(facts)[:DECISIONS]]
    return (_section("ZPRÁVY ČLOVĚKA:", messages) + _section("PRAVIDLA:", rules)
            + _section("ROZHODNUTÍ:", decisions))


def _journal_lines(facts):
    rows = [f"- {entry.get('at') or '—'} [{entry.get('status') or '?'}] {_short(entry.get('summary') or '(bez souhrnu)', 300)}"
            for entry in (facts.get("journal") or [])[-JOURNAL:]]
    return _section("DENÍK:", rows)


def _workshop_lines(facts):
    rows = [f"- {name}" + (f": {_short(doc, 200)}" if doc else "") for name, doc in (facts.get("scripts") or [])[:SCRIPTS]]
    return _section("DÍLNA:", rows)


def render(facts, limit=LIMIT):
    """Text snímku podle §3 a §3a; delší než `limit` znaků se ořízne a označí."""
    lines = [f"PROJEKT {_short(facts['name'], 120)} ({facts['project']}) · workspace {facts['workspace']}",
             f"ZÁMĚR: {_intent(facts) or '—'}", *_memory_lines(facts), "PLÁN:", *_plan(facts),
             "FRONTA ÚKOLŮ: " + _queue(facts)[0], *_queue(facts)[1:], "LÍSTKY ČEKAJÍCÍ:"]
    tickets = facts["tickets"][:TICKETS]
    lines += [f"- {t['ticketId']} {t['kind']} {_short(json.dumps(t['body'], ensure_ascii=False, sort_keys=True), 200)}" for t in tickets] or ["- žádné"]
    lines.append("POSLEDNÍ KONTROLY:")
    lines += [f"- {scope} {sha[:12]} {status}" for scope, sha, status in facts["checks"][:CHECKS]] or ["- žádné"]
    lines += _journal_lines(facts) + _workshop_lines(facts)
    text = "\n".join(lines)
    return text if len(text) <= limit else text[: limit - len(CUT)] + CUT


def _rules(facts):
    """Pravidla aplikace: schválená pravidla projektu z paměti, pak `context.rules` úkolů od nejnovějšího; bez opakování."""
    rules = []
    for rule in facts.get("rules") or []:
        text = rule.get("text")
        if _approved(rule) and isinstance(text, str) and text and text not in rules:
            rules.append(text)
    for task in sorted(facts["tasks"], key=lambda task: task["seq"], reverse=True):
        context = task["body"].get("context") if isinstance(task["body"], dict) else None
        for rule in (context or {}).get("rules", []):
            if rule not in rules:
                rules.append(rule)
    return rules[:RULES]


def view(facts, session_id=None):
    """JSON druhu `state`: `{project, intent, rules, plan, queue, myTask}`; `myTask` je úkol držený relací, jinak null."""
    stages = {card["id"]: card["stage"] for card in facts["cards"]}
    plan = ([{"id": page["id"], "name": page["name"], "stage": stages.get(page["id"], "closed"), "path": page["path"],
              "goal": page["goal"]} for page in facts["pages"][:PAGES]]
            or [{key: card[key] for key in ("id", "name", "stage")} for card in facts["cards"][:PAGES]])
    held = next((task for task in facts["tasks"] if session_id and task["status"] == "assigned"
                 and task["sessionId"] == session_id), None)
    return {"project": {"id": facts["project"], "name": facts["name"], "workspace": facts["workspace"]},
            "intent": _intent(facts), "rules": _rules(facts), "plan": plan,
            "queue": {status: sum(task["status"] == status for task in facts["tasks"]) for status in QUEUE},
            "myTask": for_worker(held) if held else None}


def state(service, project, workspace, session_id=None):
    """Stav pro agenta: `view(collect(...))`."""
    return view(collect(service, project, workspace), session_id)


def snapshot(service, project, workspace, limit=LIMIT):
    """Snímek jako text: `render(collect(...))`."""
    return render(collect(service, project, workspace), limit)
