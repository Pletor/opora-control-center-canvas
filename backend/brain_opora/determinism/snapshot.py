"""Snímek projektu pro srdce (docs/brain-heart.md §3): deterministický text bez modelu, s pevným stropem znaků.

`collect` přečte fakta (identita projektu, vyplněné nastavení webu a přebití stránek (sekce WEB, `snapshot_web.py`), zprávy člověka, pravidla a rozhodnutí z paměti Desktop v3, stránky,
oblasti a sektory plánu (sekce PLÁN nese u každého řádku plné ID uzlu),
tickety práce (sekce TICKETY PRÁCE, docs/navrhy/2026-11-03-novy-zaklad.md §3.3), čekající lístky, otevřené eskalace srdce pro člověka (sekce OTÁZKY U ČLOVĚKA), poslední vstupy vstupní brány (sekce VSTUPY), aktivní milníky s kritérii (hotovo/celkem a karty) a splněné
milníky s odloženými požadavky k otevření (sekce MILNÍKY), otevřené a odložené požadavky (sekce POŽADAVKY),
otevřené konflikty auto-rebase (sekce KONFLIKTY NÁVRHŮ, docs/oporahub-auto-rebase.md), poslední kontroly, deník dávek;
okolí srdce §3a; skripty dílny §3b; výzkumy a duely srdce ze schránky zadání §3c; řádek SCHRÁNKA s počty briefů,
platných bran a výzkumů (PR 8b, v main z prostoru posledního plánu srdce jako `opora_heart.py vault`); stav práce karet z executions
a vazeb PR, docs/brain-heart-orchestrator.md §3, včetně blokace nehotovým předchůdcem z grafu karet agent-state),
`snapshot` k nim přidá posledních 10 commitů zdroje (sekce GIT, §4) a u git projektu pracovní prostory (sekce
PROSTORY, §9 O7: doména, větev, karty volné/běží/hotové), `render` z nich bez dalšího čtení
složí text. Stejná fakta = stejný text; nic tu nezávisí na čase ani náhodě.
Každá část má vlastní strop počtu řádků a celý text se nakonec ořízne na `LIMIT` znaků.
`view` složí ze stejných faktů kompaktní JSON pro druh brány `state` (docs/brain-control-api.md §2).
"""
import json
import re
import sqlite3

from backend.brain_opora.determinism import brain_files, git_log, intake, milestones
from backend.brain_opora.determinism import snapshot_web
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.ticket import for_worker
from backend.brain_opora.determinism.ticket_model import STATES
from backend.canvas import card_gauge
from backend.canvas import opora_agent_state_dag as dag_state
from backend.canvas.architecture_graph import split
from backend.canvas.opora_auto_rebase import SOURCES as PROPOSAL_SOURCES
from backend.canvas.opora_process_sync import ProcessSync
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.brief_vault.brief_vault_details import latest_details
from backend.editor.brief_vault.brief_vault_duel_shape import summary as duel_summary
from backend.editor.brief_vault.brief_vault_gate_rules import gate_state
from backend.editor.brief_vault.brief_vault_model import effective_disciplines, latest_rows
from backend.editor.brief_vault.brief_vault_tree import live_ids
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements
from database.repositories.opora_auto_rebase import AutoRebaseStore
from database.repositories.opora_execution_pull_requests import (
    ExecutionPullRequests,
    list_execution_pull_requests,
)
from database.repositories.opora_executions import Executions
from database.repositories.tickets import HELD, TicketStore

LIMIT = 12_000  # zhruba 4k tokenů
PAGES = 20
AREAS, SECTORS = 10, 20  # oblasti a sektory v sekci PLÁN (jejich ID bere `member` a `milestone`)
TASKS = 10  # nejnovější tickety práce v sekci TICKETY PRÁCE
PLAN_LIMIT = 20  # otevřené karty z přehledu procesu
TICKETS = 10
CHECKS = 10
TEXT = 160
WORK_STATUSES = ("issued", "claimed", "in_progress", "needs_answer", "delivered", "verified", "failed")
RULES = 20
MESSAGES = 5
MESSAGE_TEXT = 400
ESCALATIONS = 5  # nejvýš řádků sekce OTÁZKY U ČLOVĚKA (otevřené eskalace srdce)
ESCALATION_TEXT = 120
ESCALATIONS_READ = 100  # kolik otevřených eskalací se čte kvůli počtu „… a další (n)“
DECISIONS = 10
JOURNAL = 5
SCRIPTS = 15
RESEARCH = 10
INTAKE_TEXT = 100  # znaků věty v sekci VSTUPY
MILESTONES = 5  # nejvýš splněných milníků v sekci MILNÍKY
ACTIVE_MILESTONES = AREAS  # nejvýš rozpracovaných aktivních milníků v sekci MILNÍKY
REQUIREMENTS = 8  # nejvýš otevřených a odložených požadavků v sekci POŽADAVKY
CONFLICTS = 5  # nejvýš řádků sekce KONFLIKTY NÁVRHŮ (konflikt = řádek)
CONFLICT_ITEMS = 2  # nejvýš polí vypsaných u konfliktu, zbytek jako „+n“
CONFLICT_VALUE = 40  # znaků hodnoty pole v konfliktu
GIT_COMMITS, GIT_CHARS = 10, 1200
SPACES_CHARS = 800  # sekce PROSTORY git projektu
FREE = "volná"  # karta bez běhu, nebo s během uvolněným či odebraným
BLOCKERS = 2  # nejvýš předchůdců vypsaných u blokované karty, zbytek jako „+n“
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


def open_cards(service, project, workspace):
    """Otevřené karty `{id, name, stage}` (nejvýš `PLAN_LIMIT`) z přehledu procesu; nečitelný přehled = prázdný."""
    try:
        items = ProcessSync(service).read(project, workspace, limit=None)["items"]
    except (ValueError, KeyError, OSError, sqlite3.Error):
        return []
    cards = [{"id": item["nodeId"], "name": item["name"], "stage": item["status"]}
             for item in items if item["status"] != "closed"]
    return cards[:PLAN_LIMIT]


def _pages(service, project, workspace):
    """`(stránky, oblasti, sektory)` z grafu plátna: stránky `{id, name, path, goal, feel}`, oblasti `{id, name}`
    a sektory `{id, name, memberOf}`; nečitelný graf = nic. ID oblastí a sektorů potřebují `member` a `milestone`."""
    try:
        nodes = service.view(project, workspace)["graph"]["nodes"]
    except (ValueError, KeyError, OSError, sqlite3.Error):
        return [], [], []
    pages, areas, sectors = [], [], []
    for node in nodes:
        site = node.get("site") if isinstance(node.get("site"), dict) else {}
        name = node.get("name") or node["id"]
        if site.get("kind") == "page":
            pages.append({"id": node["id"], "name": name, "path": site.get("path") or "",
                          "goal": site.get("goal") or "", "feel": site.get("feel") or ""})
            overrides = {key: site[key] for key in ("seo", "design") if key in site}
            if overrides:  # přebití nastavení webu (sekce WEB); stránka bez něj klíč nemá
                pages[-1]["overrides"] = overrides
        elif node.get("kind") == "area":
            areas.append({"id": node["id"], "name": name})
        elif node.get("kind") == "sector":
            sectors.append({"id": node["id"], "name": name, "memberOf": node.get("memberOf")})
    return pages, areas, sectors


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


def _vault(service, project, workspace):
    """Počty Schránky `{workspace, briefs, gates, research}`: živé briefy, jejich platné brány celkem a výzkumy.
    V main (Schránka tam nežije) prostor posledního plánu srdce, stejně jako nástroj `vault`; nečitelné = None."""
    try:
        if workspace == "main":
            workspace = brain_files.active_workspace(brain_files.brain_dir(service, project)) or workspace
        with service.reading(project):
            rows = latest_rows(service.db_for(project), project, workspace)
    except UNREADABLE:
        return None
    live, disciplines = live_ids(rows), effective_disciplines(rows)
    briefs = [rows[fid] for fid in live if rows[fid]["kind"] == "brief"]
    return {"workspace": workspace, "briefs": len(briefs),
            "gates": sum(len(gate_state(row, disciplines.get(row["fragment_id"]))["on"]) for row in briefs),
            "research": sum(rows[fid]["kind"] == "research" for fid in live)}


def _link_work(link):
    """Stav práce z vazby PR (docs/oporahub-executions.md): sloučeno (a čeká na uzavření), nebo PR #n."""
    pr = f"PR #{link['number']}" if link.get("number") else "lokální"
    if link["state"] == "merged":
        merged = f"sloučeno {str(link.get('merge_sha') or '?')[:7]}"
        # bez zápisu zpět (agent-state `merged_without_plan_writeback`) následníky dál blokuje
        return merged + (" · čeká na uzavření" if link.get("awaiting_human_close") else " · nezapsáno")
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


def _blocked(service, project, workspace, db):
    """`({karta: [předchůdce]}, {karta: jméno})` z grafu karet agent-state (`opora_agent_state_dag.facts`):
    předchůdce blokuje, dokud není sloučený se zápisem zpět nebo potvrzeně hotový. Nečitelné = nic."""
    try:
        dag = dag_state.facts(service, project, workspace, list_execution_pull_requests(db, project, workspace))
    except UNREADABLE:
        return {}, {}
    names = {key: node.get("name") or key for key, node in dag["nodes"].items()}
    return {key: value for key, value in dag["blockedBy"].items() if value}, names


def _runs(service, project, workspace, ids):
    """`{karta: štítek}` profilu běhu (`card_gauge.tag`, docs/navrhy/2026-10-30-metriky-a-spoustece.md §3) karet `ids`
    z přijatých kroků a grafu plátna; jedno čtení kontextu na snímek. Nečitelné = žádné štítky."""
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_plan_steps import steps_of

    if not ids:
        return {}
    try:
        graph = service.view(project, workspace)["graph"]
        accepted = {item["nodeId"]: item for item in OporaChangesets(service).context(project, workspace)["acceptedDocuments"]}
        index = card_gauge.graph_index(graph)
        return {node: card_gauge.tag(card_gauge.profile(index["nodes"][node], graph,
                                                        steps_of((accepted.get(node) or {}).get("fields")), index))
                for node in ids if node in index["nodes"]}
    except UNREADABLE:
        return {}


def _git(service, project, workspace):
    """Posledních `GIT_COMMITS` commitů zdroje prostoru; bez zdroje nebo s nečitelným gitem prázdné."""
    try:
        root = WorkspaceSources(service).root(project, workspace)
        return git_log.recent(root, GIT_COMMITS) if root is not None else []
    except (*UNREADABLE, *git_log.READ_ERRORS):
        return []


def _space_counts(service, project, workspace):
    """(volné, běží, hotové) karty obsahu prostoru (uzly `node` mimo architekturu) podle stavu práce z executions."""
    graph = service.view(project, workspace)["graph"]
    owned = {node["id"] for node in split(graph)[0]["nodes"]}
    cards = [node["id"] for node in graph["nodes"] if node.get("kind") == "node" and node["id"] not in owned]
    with service.reading(project):
        work = _work(service.db_for(project), project, workspace)
    states = [work.get(card, FREE) for card in cards]
    running = sum(state.startswith("běží") for state in states)
    free = sum(state == FREE for state in states)
    return free, running, len(states) - free - running


def _spaces(service, project):
    """Pracovní prostory git projektu `{id, domain, branch, free, running, done}`; jiný projekt None (sekce chybí),
    nečitelný prostor má počty None."""
    try:
        if service.project_hub.settings(project)["project"]["sourceKind"] != "git":
            return None
        rows = service.workspaces(project)
        names = {node["id"]: node.get("name") or node["id"]
                 for node in service.architecture.read(project)["graph"]["nodes"]}
    except UNREADABLE:
        return None
    spaces = []
    for row in rows:
        try:
            free, running, done = _space_counts(service, project, row["id"])
        except (*UNREADABLE, *git_log.READ_ERRORS):
            free = running = done = None
        spaces.append({"id": row["id"], "domain": names.get(row["node_id"], row["node_id"] or "—"),
                       "branch": row["branch"] or "", "free": free, "running": running, "done": done})
    return spaces


def _conflicts(db, project, workspace):
    """Otevřené konflikty auto-rebase: prvních `CONFLICTS` jako `{id, subject, items}` (nejstarší první) a jejich
    celkový počet; nečitelné = žádné."""
    try:
        found = AutoRebaseStore(db, project, workspace).conflicts("open", limit=1000)
        out = []
        for item in found[:CONFLICTS]:
            table = PROPOSAL_SOURCES.get(item.get("proposalKind"), (None,))[0]
            row = table and db.execute(f"SELECT json_extract(content,'$.subject') FROM {table} WHERE project_id=?"
                                       " AND workspace_id=? AND id=?", (project, workspace, item["proposalId"])).fetchone()
            out.append({"id": item["id"], "subject": (row[0] if row else None) or item["proposalId"],
                        "items": item.get("items") or []})
        return out, len(found)
    except UNREADABLE:
        return [], 0


def collect(service, project, workspace):
    """Fakta snímku jednoho pracovního prostoru. Neexistující projekt je 404 `project_not_found`."""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    name, goal = _identity(service, project)
    rules, decisions = _memory(service, project, workspace)
    messages, journal, scripts = _brain(service, project, workspace)
    (pages, areas, sectors), cards = _pages(service, project, workspace), open_cards(service, project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        tickets = GateTicketStore(db, project).queued(workspace, TICKETS)
        escalations = GateTicketStore(db, project).escalations(workspace, ESCALATIONS_READ)
        checks = db.execute("SELECT scope_id, sha, status FROM check_runs WHERE project_id=? AND workspace_id=?"
                            " ORDER BY recorded_at DESC, scope_id LIMIT ?", (project, workspace, CHECKS)).fetchall()
        work = _work(db, project, workspace)
        blocked, names = _blocked(service, project, workspace, db)
        entries = intake.recent(db, workspace)
        reached = milestones.reached(db, project, workspace)
        active = [item for item in (milestones.evaluate(db, project, found) for found in
                                    IntakeMilestones(db).list(workspace, ("active",))) if not item["done"]]
        wanted = IntakeRequirements(db).list(workspace, ("open", "deferred"))[-REQUIREMENTS:]
        work_tickets = TicketStore(db, project).list(workspace)
        conflicts, conflicts_total = _conflicts(db, project, workspace)
    runs = _runs(service, project, workspace, [card["id"] for card in cards])  # jen otevřené karty
    return {"workTickets": work_tickets, "conflicts": conflicts, "conflictsTotal": conflicts_total, "runs": runs, "intake": entries, "milestones": reached, "active_milestones": active, "requirements": wanted, "work": work, "blocked": blocked, "names": names, "project": project, "name": name, "workspace": workspace, "goal": goal, "pages": pages, "areas": areas, "sectors": sectors, "cards": cards,
            "tickets": tickets, "escalations": escalations, "checks": [tuple(row) for row in checks], "messages": messages,
            "rules": rules, "decisions": decisions, "journal": journal, "scripts": scripts,
            "research": _research(service, project, workspace), "vault": _vault(service, project, workspace),
            "site": service.project_hub.site_settings(project)}


def _intent(facts):
    """Záměr z cíle projektu, jinak z domovské stránky; žádný = prázdný text."""
    if facts["goal"].strip():
        return _short(facts["goal"], 400)
    home = next((page for page in facts["pages"] if page["path"].rstrip("/") == ""), None)
    if home and (home["goal"] or home["feel"]):
        return _short(" · ".join(part for part in (home["goal"], home["feel"]) if part), 400)
    return ""


def _work_first(facts, cards):
    """Karty s pracovním kontextem před holými (před ořezem na PAGES): s prací (běží, PR, sloučeno), blokované,
    úkolové `[task]`, zbytek; v každé skupině zůstává pořadí grafu. Jinak by 37 architektonických karet vytlačilo
    ty, které srdce zrovna potřebuje s plným ID."""
    work, blocked = facts.get("work") or {}, facts.get("blocked") or {}

    def rank(card):
        return 0 if work.get(card["id"], FREE) != FREE else 1 if card["id"] in blocked else 2 if card["name"].startswith("[task]") else 3
    return sorted(cards, key=rank)


def _plan(facts):
    """Řádky sekce PLÁN, každý s plným ID uzlu (bere ho `member`, `milestone`, `--node`, `"@<id>"`): stránky, otevřené
    karty mimo stránky, oblasti a sektory. Srdce tak ID nehledá přes `ctx tree`, `plan-of` ani nový `snapshot`."""
    stages = {card["id"]: card["stage"] for card in facts["cards"]}
    work, runs = facts.get("work"), facts.get("runs") or {}

    def doing(node):  # stav práce z executions (§3 orchestrátoru) a štítek běhu; fakta bez nich je nepíšou
        return ("" if work is None else f" · {_doing(facts, node)}") + (f" · {runs[node]}" if node in runs else "")

    pages = facts["pages"][:PAGES]
    rows = [f"- {_short(page['name'], 80)} · {page['id']} · {page['path'] or '—'} · {stages.get(page['id'], 'closed')}"
            + doing(page["id"]) + (f" · cíl: {_short(page['goal'], 120)}" if page["goal"] else "") for page in pages]
    shown = {page["id"] for page in pages}
    rows += [f"- {_short(card['name'], 80)} · {card['id']} · {card['stage']}" + doing(card["id"])
             for card in _work_first(facts, [card for card in facts["cards"] if card["id"] not in shown])[:PAGES]]
    rows += [f"- oblast {_short(area['name'], 60)} · {area['id']}" for area in (facts.get("areas") or [])[:AREAS]]
    rows += [f"- sektor {_short(sector['name'], 60)} · {sector['id']}"
             + (f" · oblast {sector['memberOf']}" if sector.get("memberOf") else "")
             for sector in (facts.get("sectors") or [])[:SECTORS]]
    return rows or ["- (prázdný plán)"]


def _waiting_on(work, node):
    """Stav předchůdce, na kterého blokovaná karta čeká: otevřený PR, nezapsané sloučení, běh nebo volná."""
    state = work.get(node, FREE)
    return state + " otevřený" if state.startswith("PR #") and not state.endswith("zavřený") else state


def _doing(facts, node):
    """Stav práce karty; volná karta s nehotovým předchůdcem je „blokovaná – čeká na <jméno>: <jeho stav>“."""
    work = facts.get("work") or {}
    state, blockers = work.get(node, FREE), (facts.get("blocked") or {}).get(node)
    if state != FREE or not blockers:
        return state
    names = facts.get("names") or {}
    parts = [f"{_short(names.get(item, item), 40)}: {_waiting_on(work, item)}" for item in blockers[:BLOCKERS]]
    more = f" +{len(blockers) - BLOCKERS}" if len(blockers) > BLOCKERS else ""
    return "blokovaná – čeká na " + "; ".join(parts) + more


def _work_ticket_lines(facts):
    """Sekce TICKETY PRÁCE: počty podle stavu a nejnovější tickety (titulek = první řádek „co postavit“, karta,
    oddělení kanceláře, počet následníků karty, piny Brainu `plugin@sha12`, u drženého kdo a od kdy). Srdce podle ní nevydává stejnou práci dvakrát a ruší, co už nedává smysl."""
    tickets = facts.get("workTickets") or []
    counts = {status: sum(item["status"] == status for item in tickets) for status in WORK_STATUSES}
    head = "TICKETY PRÁCE: " + " · ".join(f"{status} {count}" for status, count in counts.items())
    last = sorted(tickets, key=lambda item: item["seq"], reverse=True)[:TASKS]
    return [head, *(f"- [{item['status']}] {_short(item['body']['build'].splitlines()[0], 100)} ({item['ticketId']})"
                    + (f" · karta {item['machine']['cardId']}" if item["machine"]["cardId"] else "")
                    + (f" · oddělení {item['machine']['department']}" if item["machine"].get("department") else "")
                    + (f" · následníci {len(item['machine']['successors'])}" if item["machine"].get("successors") else "")
                    + (" · piny " + ", ".join(f"{pin['plugin']}@{pin['version'][:12]}" for pin in item["machine"]["pins"])
                       if item["machine"].get("pins") else "")
                    + (f" · drží {item['sessionId']} od {item['updatedAt']}" if item["sessionId"] else "")
                    for item in last)]


def _vault_lines(facts):
    """SCHRÁNKA: jeden řádek s počty a nápovědou `vault ls`; prázdná nebo nečitelná Schránka = řádek chybí."""
    vault = facts.get("vault")
    if not vault or not (vault["briefs"] or vault["research"]):
        return []
    where = f" (prostor {vault['workspace']})" if vault["workspace"] != facts["workspace"] else ""
    return [(f"SCHRÁNKA{where}: {vault['briefs']} briefů, {vault['gates']} bran, {vault['research']} výzkumů"
             " · plánuj z ní: python opora_heart.py vault ls | vault show ID | vault plan")]


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
                + (f" (přes {_short(entry['via'], 80)})" if isinstance(entry.get("via"), str) and entry["via"] else "")
                for entry in (facts.get("messages") or [])[-MESSAGES:]]
    rules = [f"- {_short(rule.get('text'), 300)}" + ("" if _approved(rule) else " (návrh)")
             for rule in _project_rules(facts)[:RULES]]
    decisions = [f"- {'[připnuto] ' if item.get('pinned') is True else ''}{_short(item.get('text'), 300)}"
                 + (f" · karta {item['nodeId']}" if item.get("nodeId") else "")
                 + (f" · {item['path']}" if item.get("path") else "") for item in _decisions(facts)[:DECISIONS]]
    return (_section("ZPRÁVY ČLOVĚKA:", messages) + _section("PRAVIDLA:", rules)
            + _section("ROZHODNUTÍ:", decisions))


def _escalation_lines(facts):
    """Sekce OTÁZKY U ČLOVĚKA (docs/brain-heart-channel.md §6): otevřené eskalace srdce od nejnovější, s plným ID,
    ať je srdce může stáhnout (`escalate --withdraw`) a neptá se znovu. Bez otevřených sekce chybí."""
    escalations = facts.get("escalations") or []
    if not escalations:
        return []
    rows = [f"- {item['ticketId']} · {item['createdAt']} · {_short(item['body'].get('text'), ESCALATION_TEXT)}"
            for item in escalations[:ESCALATIONS]]
    more = len(escalations) - ESCALATIONS
    return ["OTÁZKY U ČLOVĚKA:", *rows, *([f"… a další ({more})"] if more > 0 else [])]


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


def _intake_lines(facts):
    """VSTUPY: poslední vstupy brány, které srdce ještě nepotvrdilo (docs/navrhy/2026-10-30-vstupni-brana.md §4):
    ID, stanovisko, u Jevu jistota a oblast, začátek věty. Žádné = sekce chybí, ať snímek bez brány zůstane stejný."""
    def mark(entry):
        jev = entry.get("layer") == "jev" and isinstance(entry.get("confidence"), (int, float))
        return ((f" (jev {entry['confidence']:.2f})" if jev else "")
                + (f" · oblast {entry['areaId']}" if entry.get("areaId") else ""))
    rows = [f"- {entry['id']} · {entry['verdict']}{mark(entry)} · {_short(entry['text'], INTAKE_TEXT)}"
            for entry in (facts.get("intake") or [])[:intake.RECENT]]
    return ["VSTUPY:", *rows] if rows else []


def _active_line(item):
    """Rozpracovaný aktivní milník s plným ID, aby ho srdce nezakládalo podruhé: oblast, kritéria hotovo/celkem a karty."""
    done = sum(criterion["done"] for criterion in item["criteria"])
    parts = [f"{criterion['id']} {'hotovo' if criterion['done'] else 'čeká'} (" + ", ".join(
        card["id"] for card in criterion["cards"]) + ")" for criterion in item["criteria"]]
    return (f"- milník {item['id']} „{_short(item['title'], 80)}“ aktivní · oblast {item['areaId']} · kritéria "
            f"{done}/{len(item['criteria'])}: " + "; ".join(parts))


def _milestone_lines(facts):
    """MILNÍKY: rozpracované aktivní milníky prostoru (ID, oblast, kritéria) a splněné aktivní milníky prostoru a odložené požadavky s podmínkou na ně (spouštěč `milestone.done`,
    docs/navrhy/2026-10-30-metriky-a-spoustece.md §4). Stav požadavku nepřepíná, rozhodne srdce. Žádné = bez sekce."""
    rows = [_active_line(item) for item in (facts.get("active_milestones") or [])[:ACTIVE_MILESTONES]]
    rows += [f"- milník {item['milestone']['id']} „{_short(item['milestone']['title'], 80)}“ splněn – odložené"
            f" požadavky k otevření: {', '.join(rq['id'] for rq in item['deferred']) or 'žádné'}"
            for item in (facts.get("milestones") or [])[:MILESTONES]]
    return ["MILNÍKY:", *rows] if rows else []


def _requirement_lines(facts):
    """POŽADAVKY: posledních `REQUIREMENTS` otevřených a odložených požadavků prostoru (ID pro `intake --requirement
    rq_…`, ať srdce upřesnění připojí místo nového zadání). Žádné = bez sekce."""
    def head(item):
        return item["status"] + (f" (po {item['openCondition']})" if item["status"] == "deferred" else "")
    rows = [f"- {item['id']} · {head(item)}" + (f" · oblast {item['areaId']}" if item.get("areaId") else "")
            + f" · {_short(item['title'], 80)}" for item in facts.get("requirements") or []]
    return ["POŽADAVKY:", *rows] if rows else []


def _value(value):
    return _short(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True),
                  CONFLICT_VALUE)


def _conflict_lines(facts):
    """KONFLIKTY NÁVRHŮ: otevřené konflikty auto-rebase s plným ID (bere ho `conflict --resolve`), zkrácený předmět
    návrhu a pole `klíč: náš → hodnota | přijato hodnota`. Nejvýš `CONFLICTS` řádků; žádné = bez sekce."""
    found = (facts.get("conflicts") or [])[:CONFLICTS]
    total = max(facts.get("conflictsTotal") or 0, len(found))
    rows = []
    for item in found:
        fields = [f"{field.get('key')}: náš → {_value(field.get('ours'))} | přijato {_value(field.get('theirs'))}"
                  for field in item["items"][:CONFLICT_ITEMS]]
        rest = len(item["items"]) - CONFLICT_ITEMS
        rows.append(f"- {item['id']} · {_short(item['subject'], 60)} · " + "; ".join(fields)
                    + (f"; +{rest}" if rest > 0 else ""))
    if total > CONFLICTS:
        rows[-1] = f"- … a další ({total - CONFLICTS + 1})"
    return ["KONFLIKTY NÁVRHŮ:", *rows] if rows else []


def _git_lines(facts):
    rows, size = [], 0
    for line in (facts.get("git") or [])[:GIT_COMMITS]:
        row = f"- {_short(line, 200)}"
        if size + len(row) + 1 > GIT_CHARS:
            break
        rows.append(row)
        size += len(row) + 1
    return _section("GIT:", rows)


def _space_lines(facts):
    """PROSTORY (jen git projekt): plné ID prostoru (to bere `--workspace`), doména, větev, když není `work/<id>`,
    a karty volné/běží/hotové; nejvýš `SPACES_CHARS` znaků."""
    rows, size = [], 0
    for space in facts["spaces"]:
        branch = "" if space["branch"] == "work/" + space["id"] else f" · {_short(space['branch'], 60)}"
        counts = ("karty ?" if space["free"] is None
                  else f"karty volné {space['free']} · běží {space['running']} · hotové {space['done']}")
        row = f"- {space['id']} · doména {_short(space['domain'], 60)}{branch} · {counts}"
        if size + len(row) + 1 > SPACES_CHARS - 30:  # místo na řádek „… a další“
            rows.append(f"- … a další ({len(facts['spaces']) - len(rows)})")
            break
        rows.append(row)
        size += len(row) + 1
    return _section("PROSTORY:", rows)


def render(facts, limit=LIMIT):
    """Text snímku podle §3, §3a, §3b a §3c; delší než `limit` znaků se ořízne a označí."""
    lines = [f"PROJEKT {_short(facts['name'], 120)} ({facts['project']}) · workspace {facts['workspace']}",
             f"ZÁMĚR: {_intent(facts) or '—'}", *snapshot_web.lines(facts.get("site"), facts["pages"]), *_memory_lines(facts), *_escalation_lines(facts),
             "PLÁN:", *_plan(facts), *_work_ticket_lines(facts), *_vault_lines(facts), "LÍSTKY ČEKAJÍCÍ:"]
    tickets = facts["tickets"][:TICKETS]
    lines += [f"- {t['ticketId']} {t['kind']} {_short(json.dumps(t['body'], ensure_ascii=False, sort_keys=True), 200)}" for t in tickets] or ["- žádné"]
    lines += _intake_lines(facts) + _requirement_lines(facts) + _milestone_lines(facts) + _conflict_lines(facts)
    lines.append("POSLEDNÍ KONTROLY:")
    lines += [f"- {scope} {sha[:12]} {status}" for scope, sha, status in facts["checks"][:CHECKS]] or ["- žádné"]
    lines += _git_lines(facts) + (_space_lines(facts) if facts.get("spaces") is not None else [])
    lines += _journal_lines(facts) + _workshop_lines(facts) + _research_lines(facts)
    text = "\n".join(lines)
    return text if len(text) <= limit else text[: limit - len(CUT)] + CUT


def _rules(facts):
    """Pravidla aplikace: schválená pravidla projektu z paměti, bez opakování."""
    rules = []
    for rule in facts.get("rules") or []:
        text = rule.get("text")
        if _approved(rule) and isinstance(text, str) and text and text not in rules:
            rules.append(text)
    return rules[:RULES]


def view(facts, session_id=None):
    """JSON druhu `state`: `{project, intent, rules, plan, tickets, myTicket}`; `tickets` jsou počty ticketů práce
    prostoru podle stavu, `myTicket` ticket držený relací (claimed až delivered, jako `ticket.request`), jinak null."""
    stages = {card["id"]: card["stage"] for card in facts["cards"]}
    plan = ([{"id": page["id"], "name": page["name"], "stage": stages.get(page["id"], "closed"), "path": page["path"],
              "goal": page["goal"]} for page in facts["pages"][:PAGES]]
            or [{key: card[key] for key in ("id", "name", "stage")} for card in _work_first(facts, facts["cards"])[:PAGES]])
    work = facts.get("workTickets") or []
    held = next((item for item in work if session_id and item["status"] in HELD and item["sessionId"] == session_id),
                None)
    return {"project": {"id": facts["project"], "name": facts["name"], "workspace": facts["workspace"]},
            "intent": _intent(facts), "rules": _rules(facts), "plan": plan,
            "tickets": {status: sum(item["status"] == status for item in work) for status in STATES},
            "myTicket": for_worker(held) if held else None}


def state(service, project, workspace, session_id=None):
    """Stav pro agenta: `view(collect(...))`."""
    return view(collect(service, project, workspace), session_id)


def snapshot(service, project, workspace, limit=LIMIT):
    """Snímek jako text: `render(collect(...))` a commity zdroje (git jen tady, `state` pro pracovníky ho nečte)."""
    facts = collect(service, project, workspace)
    return render({**facts, "git": _git(service, project, workspace), "spaces": _spaces(service, project)}, limit)
