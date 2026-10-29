"""Snímek projektu pro srdce (docs/brain-heart.md §3): deterministický text bez modelu, s pevným stropem znaků.

`collect` přečte fakta (identita projektu, zprávy člověka, pravidla a rozhodnutí z paměti Desktop v3, stránky plánu,
fronta úkolů, čekající lístky, poslední kontroly, deník dávek; okolí srdce §3a; skripty dílny §3b; výzkumy a duely
srdce ze schránky zadání §3c; stav práce karet z executions a vazeb PR, docs/brain-heart-orchestrator.md §3),
`snapshot` k nim přidá posledních 10 commitů zdroje (sekce GIT, §4), `render` z nich bez dalšího čtení
složí text. Stejná fakta = stejný text; nic tu nezávisí na čase ani náhodě.
Každá část má vlastní strop počtu řádků a celý text se nakonec ořízne na `LIMIT` znaků.
`view` složí ze stejných faktů kompaktní JSON pro druh brány `state` (docs/brain-control-api.md §2).
"""
import json
import re
import sqlite3

from backend.brain_opora.determinism import brain_files, git_log
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_queue import for_worker, open_cards
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.brief_vault.brief_vault_details import latest_details
from backend.editor.brief_vault.brief_vault_duel_shape import summary as duel_summary
from backend.editor.brief_vault.brief_vault_model import latest_rows
from backend.editor.brief_vault.brief_vault_tree import live_ids
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_tasks import HeartTaskStore
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions

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
RESEARCH = 10
GIT_COMMITS, GIT_CHARS = 10, 1200
FREE = "volná"  # karta bez běhu, nebo s během uvolněným či odebraným
NEXT_LINE = re.compile(r"Další krok: (plan|spike|duel|ask|stop)\b")
HEART = "heart"  # autor výzkumů a duelů srdce ve schránce (agent `heart`)
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


def research_next(approach):
    """`next` výzkumného stolu (§3d) z prvního řádku `approach` („Další krok: <next> – …“); schránka pole
    `next` nemá a její schéma se nemění. Bez něj (výzkum §3c, člověk) prázdný text."""
    match = NEXT_LINE.match(approach or "")
    return match.group(1) if match else ""


def _research(service, project, workspace):
    """Živé fragmenty `research` a `duel`, které založilo srdce, s výtahem podrobností; nejnovější první."""
    try:
        with service.reading(project):
            db = service.db_for(project)
            rows = latest_rows(db, project, workspace)
            mine = {row[0] for row in db.execute(
                "SELECT fragment_id FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? AND revision=1"
                " AND by=? AND kind IN ('research', 'duel')", (project, workspace, HEART))}
            ids = sorted(mine & live_ids(rows), key=lambda fid: (rows[fid]["saved_at"], fid), reverse=True)[:RESEARCH]
            details = latest_details(db, project, workspace, ids)
    except UNREADABLE:
        return []
    items = []
    for fragment_id in ids:
        fields = (details.get(fragment_id) or {}).get("fields") or {}
        item = {"id": fragment_id, "kind": rows[fragment_id]["kind"], "title": rows[fragment_id]["title"]}
        if item["kind"] == "duel" and isinstance(fields.get("duel"), dict):
            summary = duel_summary(fields["duel"])
            item.update(status=summary["status"], outcome=summary["outcome"], p=summary["p"])
        elif isinstance(fields.get("research"), dict):
            research = fields["research"]
            item.update(status=research["status"], verdict=research["verdict"], confidence=research["confidence"],
                        next=research_next(research.get("approach")))
        items.append(item)
    return items


def _link_work(link):
    """Stav práce z vazby PR (docs/oporahub-executions.md): sloučeno (a čeká na uzavření), nebo PR #n."""
    pr = f"PR #{link['number']}" if link.get("number") else "lokální"
    if link["state"] == "merged":
        merged = f"sloučeno {str(link.get('merge_sha') or '?')[:7]}"
        return merged + (" · čeká na uzavření" if link.get("awaiting_human_close") else "")
    return pr + (" zavřený" if link["state"] == "closed" else "")


def work_states(executions, links):
    """`{nodeId: text}` z nejnovějšího běhu karty a jeho vazby PR; bez vazby rozhoduje stav běhu.
    `executions` a `links` jsou od nejnovějšího (tak je vrací `Executions.history` a `ExecutionPullRequests.listing`)."""
    by_execution, by_node, work = {}, {}, {}
    for link in links:
        by_execution.setdefault(link["execution_id"], link)
        by_node.setdefault(link["node_id"], link)
    for record in executions:
        node = record.get("nodeId")
        if node in work:
            continue
        link = by_execution.get(record.get("executionId"))
        state = record.get("state")
        work[node] = (_link_work(link) if link else f"běží ({record.get('owner') or '?'})" if state == "running"
                      else "odevzdáno" if state == "reported" else FREE)
    for node, link in by_node.items():
        work.setdefault(node, _link_work(link))
    return work


def _work(db, project, workspace):
    try:
        return work_states(Executions(db, project, workspace).history(),
                           ExecutionPullRequests(db, project, workspace).listing())
    except UNREADABLE:
        return {}


def _git(service, project, workspace):
    """Posledních `GIT_COMMITS` commitů zdroje prostoru; bez zdroje nebo s nečitelným gitem prázdné."""
    try:
        root = WorkspaceSources(service).root(project, workspace)
        return git_log.recent(root, GIT_COMMITS) if root is not None else []
    except (*UNREADABLE, *git_log.READ_ERRORS):
        return []


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
        work = _work(db, project, workspace)
    return {"work": work, "project": project, "name": name, "workspace": workspace, "goal": goal, "pages": pages, "cards": cards,
            "tasks": tasks, "tickets": tickets, "checks": [tuple(row) for row in checks], "messages": messages,
            "rules": rules, "decisions": decisions, "journal": journal, "scripts": scripts,
            "research": _research(service, project, workspace)}


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
    work = facts.get("work")

    def doing(node):  # stav práce z executions (§3 orchestrátoru); fakta bez `work` ho nepíšou
        return "" if work is None else f" · {work.get(node, FREE)}"

    if facts["pages"]:
        rows = [f"- {_short(page['name'], 80)} · {page['path'] or '—'} · {stages.get(page['id'], 'closed')}"
                + doing(page["id"]) + (f" · cíl: {_short(page['goal'], 120)}" if page["goal"] else "")
                for page in facts["pages"][:PAGES]]
    else:
        rows = [f"- {_short(card['name'], 80)} · {card['id']} · {card['stage']}" + doing(card["id"])
                for card in facts["cards"][:PAGES]]
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


def _research_lines(facts):
    rows = []
    for item in (facts.get("research") or [])[:RESEARCH]:
        head = f"- {'duel' if item['kind'] == 'duel' else 'výzkum'} {_short(item['title'], 100)} ({item['id']})"
        if item["kind"] == "duel":
            p = item.get("p")
            rows.append(head + f" · {item.get('outcome') or item.get('status') or '?'}"
                        + (f" · p {p:.2f}" if isinstance(p, (int, float)) else ""))
        else:
            rows.append(head + f" · {item.get('verdict') or '?'}"
                        + (f"/{item['confidence']}" if item.get("confidence") else "")
                        + (f" · next {item['next']}" if item.get("next") else "") + f" · {item.get('status') or '?'}")
    return _section("VÝZKUM:", rows)


def _git_lines(facts):
    rows, size = [], 0
    for line in (facts.get("git") or [])[:GIT_COMMITS]:
        row = f"- {_short(line, 200)}"
        if size + len(row) + 1 > GIT_CHARS:
            break
        rows.append(row)
        size += len(row) + 1
    return _section("GIT:", rows)


def render(facts, limit=LIMIT):
    """Text snímku podle §3, §3a, §3b a §3c; delší než `limit` znaků se ořízne a označí."""
    lines = [f"PROJEKT {_short(facts['name'], 120)} ({facts['project']}) · workspace {facts['workspace']}",
             f"ZÁMĚR: {_intent(facts) or '—'}", *_memory_lines(facts), "PLÁN:", *_plan(facts),
             "FRONTA ÚKOLŮ: " + _queue(facts)[0], *_queue(facts)[1:], "LÍSTKY ČEKAJÍCÍ:"]
    tickets = facts["tickets"][:TICKETS]
    lines += [f"- {t['ticketId']} {t['kind']} {_short(json.dumps(t['body'], ensure_ascii=False, sort_keys=True), 200)}" for t in tickets] or ["- žádné"]
    lines.append("POSLEDNÍ KONTROLY:")
    lines += [f"- {scope} {sha[:12]} {status}" for scope, sha, status in facts["checks"][:CHECKS]] or ["- žádné"]
    lines += _git_lines(facts) + _journal_lines(facts) + _workshop_lines(facts) + _research_lines(facts)
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
    """Snímek jako text: `render(collect(...))` a commity zdroje (git jen tady, `state` pro pracovníky ho nečte)."""
    facts = collect(service, project, workspace)
    return render({**facts, "git": _git(service, project, workspace)}, limit)
