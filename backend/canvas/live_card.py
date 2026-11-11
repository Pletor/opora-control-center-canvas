"""Živá karta (docs/navrhy/2026-11-11-platno-3-folie.md, „K1: kontrakt živé karty“): jedna odpověď pro líc i rub.

`gather` jen čte existující zdroje (stopa karty, ProcessSync, agent-state, node-brief, tickety a Linie, plátno logiky
a sken stránky plátna 2, pozorované ceny běhů); `compose` je čistá projekce do tvaru kontraktu; `layer` z ní vybere
vrstvu `souhrn` / `tvar` pro node-brief. Sekce bez dat je `null` a nese `source` (adresu endpointu). Nic neukládá,
model nevolá.
"""
from urllib.parse import quote, urlencode

from backend.agi_pletor.linie import trace as trace_mod
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.graph import recent_prs
from backend.brain_opora.determinism import triggers
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas import card_trail, card_trail_read, plan_future, plan_reality
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_card_done import REQUIREMENTS
from backend.canvas.opora_event_stage import confirmed_nodes
from backend.canvas.opora_execution_observers import spent
from backend.canvas.opora_process_sync import ProcessSync
from backend.editor.agent_packet.node_brief import NodeBrief
from backend.project.architecture import page_plan, page_plan_scan

RECENT = 30
LAYERS = ("souhrn", "tvar")
BLOCK_STATUS = {"met": "ok", "blocked": "bad"}
# Požadavky definice hotovo (`opora_card_done.card_done_state`) česky pro člověka i agenta; `key` zůstává v položce.
REQUIREMENT_TEXT = {
    "steps": "Kroky plánu hotové", "card_acceptance": "Přijetí karty doloženo", "gate_ready": "Brána revize připravena",
    "merged": "Sloučeno do main", "plan_written_back": "Plán zapsán zpět", "journeys": "Cesty zákazníka ověřeny",
    "human_close": "Karta uzavřena",  # zavírá server sám po splnění ostatního (`by: opora`), ruční zavření je volitelné
}
TRIGGER_WHEN = {
    "card.too_big": "štítek XL u karty ready",
    "card.retry": f"≥ {triggers.RETRY_FAILURES} běhy skončily bez výsledku",
    "card.step_failed": "odevzdaný běh nahlásil krok failed a nemá PR",
    "card.stalled": f"běh starší než {triggers.STALL_FACTOR}× medián štítku bez události kroku",
    "card.over_budget": f"cena karty > {triggers.BUDGET_FACTOR}× medián štítku",
    "card.failing": f"Kancelář hlásí opakovaně selhávající testy, nebo stejný nástroj selhal {triggers.FAIL_STREAK}× v řadě",
    "card.drift": "dělník editoval soubor mimo očekávané soubory karty",
    "card.collision": "sloučení otevřené práce karty skončí konfliktem, nebo zasáhne kartu s otevřenou prací nad stejnými soubory",
}


def state_of(node, sync, *, merged=False, held=False, dry=False):
    """Tvar karty (F3), první platné pravidlo vyhrává:
    leaf = uzavřená karta (ProcessSync `closed`) nebo sloučený PR; dry = ruční blokace Linie (slepá cesta);
    bud = běží nebo odevzdala (`running`, `reported`), nebo ji drží dělník (lease, rozpracovaný ticket);
    prop = pracovní zadání čeká na přijetí (`needs-acceptance`); goal = karta GOAL (`goal_mode: until_checks_pass`);
    seed = jen záměr (ostatní: needs-plan, needs-steps, ready, blocked předchůdcem, unavailable, mimo ProcessSync)."""
    status = (sync or {}).get("status")
    if status == "closed" or merged:
        return "leaf"
    if dry:
        return "dry"
    if status in ("running", "reported") or held:
        return "bud"
    if status == "needs-acceptance":
        return "prop"
    if (node or {}).get("goal_mode") == "until_checks_pass":
        return "goal"
    return "seed"


def progress_of(sync):
    steps = (sync or {}).get("steps") or {}
    return round(100 * steps.get("done", 0) / steps["total"]) if steps.get("total") else None


def _query(project, workspace, node, key="nodeId"):
    return urlencode({"project": project, "workspace": workspace, key: node})


def _linie(service, project, workspace, tickets, root, folder, pr_lookup):
    """Ticket Linie karty (`for_card`, první s `work.mark`), jeho osy (`work.present`) a cesta (`trace`); jinak None."""
    ticket = next((item for item in tickets if (item.get("work") or {}).get("mark")), None)
    if ticket is None or folder is None:
        return None
    with service.reading(project):
        shown = work_mod.present(service, project, ticket)
    try:
        traced = trace_mod.trace(service, project, workspace, root, ticket["work"]["mark"], folder, pr_lookup=pr_lookup)
    except GateError:
        return None
    return {"ticket": ticket, "shown": shown, "trace": traced}


def _plane(service, project, workspace, node, graph, by_id):
    """Vazba na plátno 2: uzel je prvek logiky (`element` pod stránkou), karta plátna 3 s vazbou „dokládá“ na prvek
    (`plan_reality.element_of`), nebo sama stránka. `(page, flow, scan, element)`."""
    element = plan_reality.element_of(node, graph["nodes"], graph["edges"])
    page = by_id.get(element.get("parentId")) if element else node
    if not page or (page.get("site") or {}).get("kind") != "page":
        return None, None, None, None
    return (page, plan_reality.flow_of(service, project, element),
            _latest_scan(service, project, workspace, page["id"]), element)


def _latest_scan(service, project, workspace, page_id):
    try:
        return page_plan_scan.latest(service, project, workspace, page_id, adopted=True)
    except GateError:
        return None


def _domain(service, project, workspace, node, graph):
    """Uzel = doména webu plátna 2 (`site.kind application`, id = `domainId`): stránky, jejichž nejbližší doména nad
    nimi je tento uzel (jako navigace v `specification_context`), s posledním skenem a prvky logiky; jinak None."""
    if (node.get("site") or {}).get("kind") != "application":
        return None
    pages = page_plan.domain_pages(graph, node["id"])
    elements = {page["id"]: [item["id"] for item in page_plan.page_elements(graph, page["id"])] for page in pages}
    done = confirmed_nodes(service.db_for(project), project, workspace, [i for ids in elements.values() for i in ids])
    return [{"page": page, "scan": _latest_scan(service, project, workspace, page["id"]),
             "elements": len(elements[page["id"]]), "done": len(done & set(elements[page["id"]]))} for page in pages]


def _agent_state(service, project, workspace, node):
    """Karta z agent-state (stránky `cards[]` po 100) a rozhodnutí člověka, která na ni míří."""
    offset, card, decisions = 0, None, []
    while card is None:
        state = AgentState(service).read(project, workspace, offset)
        card = next((item for item in state["cards"] if item["nodeId"] == node), None)
        decisions = state["decisions"]
        if state["cardsNextOffset"] is None:
            break
        offset = state["cardsNextOffset"]
    return card, decisions


def gather(service, project, workspace, node, *, root=None, folder=None, pr_lookup=recent_prs):
    """Syrová fakta živé karty; `ValueError` = neplatný rozsah nebo uzel. Bez `folder` (Pletor) Linie chybí."""
    trail = card_trail_read.gather(service, project, workspace, node)
    graph = service.view(project, workspace)["graph"]
    by_id = {item["id"]: item for item in graph["nodes"]}
    if node not in by_id:
        raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
    sync = {item["nodeId"]: item for item in ProcessSync(service).read(project, workspace, limit=None)["items"]}
    agent, decisions = _agent_state(service, project, workspace, node)
    page, flow, scan, element = _plane(service, project, workspace, by_id[node], graph, by_id)
    known, code = plan_reality.facts(service, project, workspace, graph), plan_reality.root_of(service, project, workspace) or root
    mirror = plan_reality.for_card(service, project, workspace, node, code, known)
    return {"project": project, "workspace": workspace, "nodeId": node, "trail": trail, "graph": graph,
            "sync": sync, "brief": NodeBrief(service).build(project, workspace, node), "agent": agent,
            "decisions": decisions, "costs": spent(service, project, workspace),
            "linie": _linie(service, project, workspace, trail["tickets"], root, folder, pr_lookup),
            "page": page, "flow": flow, "scan": scan, "element": element,
            "mirror": mirror,
            "future": plan_future.card(code, node, graph["nodes"], graph["edges"], known["works"]) if code else None,
            "domain": _domain(service, project, workspace, by_id[node], graph)}


def _vision(brief, q, leaf):
    goal = brief["goal"]["acceptance"]
    items = [{"text": text, "status": "ok" if leaf or brief.get("acceptanceEvidence") else "wait"}
             for text in (goal if isinstance(goal, list) else [goal]) if isinstance(text, str) and text.strip()]
    statuses = {block["id"]: block["state"]["status"] for block in brief["blocks"]}
    items += [{"text": item["condition"], "status": BLOCK_STATUS.get(statuses.get(item["blockId"]), "wait")}
              for item in brief["definitionOfDone"]["blockConditions"]]
    return {"source": f"/api/desktop-v3/node-brief?{q}", "items": items} if items else None


def _reality(done, q, linie):
    if not done:
        return None
    missing = set(done.get("missing") or [])
    value = {"source": f"/api/oporahub/card-trail?{q}",
             "items": [{"key": name, "text": REQUIREMENT_TEXT[name], "status": "miss" if name in missing else "ok"}
                       for name in REQUIREMENTS]}
    merged = ((linie or {}).get("ticket") or {}).get("work", {}).get("merged") or {}
    return value | ({"sha": merged["sha"]} if merged.get("sha") else {})


MIRROR_STATUS = {"matched": "ok", "missing": "miss", "extra": "bad", "symbols": "ok"}


def _mirror(found, q):
    """Zrcadlo kódu z folie (`plan_reality`): shoda, chybí, navíc a co přibylo; bez commitů i očekávání do F1."""
    if not found or (found["evidence"] is None and not found["missing"]):
        return {"available": False, "milestone": "F1"}
    items = [{"kind": item["kind"], "name": item["name"], "path": item["path"], "line": item.get("line"),
              "status": status, "text": item.get("note") or item.get("change") or item["source"]}
             for key, status in MIRROR_STATUS.items() for item in found[key]]
    return {"available": True, "source": f"/api/oporahub/plan-reality?{q}", "items": items,
            "counts": plan_reality.counts(found), "evidence": found["evidence"]}


def _future(found):
    """Budoucnost po sloučení (F4); karta bez otevřené práce ji nemá."""
    return {"available": True, **found} if found else {"available": False}


def _edges(node, graph, reports, states, names):
    found = []
    for edge in graph["edges"]:
        if node not in (edge["source"], edge["target"]):
            continue
        other = edge["target"] if edge["source"] == node else edge["source"]
        report = reports.get(edge["id"]) if isinstance(reports.get(edge["id"]), dict) else {}
        found.append({"edgeId": edge["id"], "dir": "out" if edge["source"] == node else "in",
                      "relation": edge.get("relation"), "carries": edge.get("carries"),
                      "other": {"nodeId": other, "title": names.get(other), "state": states.get(other)},
                      "last": report.get("summary") or report.get("handoff") or None})
    return found


def _element(facts):
    """Prvek plátna 2 karty (u karty plátna 3 cíl její vazby „dokládá“), jinak uzel karty sám."""
    return facts.get("element") or next(item for item in facts["graph"]["nodes"] if item["id"] == facts["nodeId"])


def _flow(facts, q):
    if facts["flow"] is None or facts["page"] is None:
        return None
    node = _element(facts)
    lists = plan_reality.flow_lists(facts["flow"])
    return {"source": f"/api/library/project-flows?{urlencode({'project': facts['project'], 'nodeId': node['id']})}",
            "pageId": facts["page"]["id"], "elementId": node["id"], "name": node["name"], **lists}


def _output(facts, linie):
    scan, page = facts["scan"], facts["page"]
    preview = ((linie or {}).get("trace") or {}).get("preview")
    scope = urlencode({"project": facts["project"], "workspace": facts["workspace"]})
    captures = []
    for entry in facts.get("domain") or []:  # doména: celostránkový snímek posledního skenu každé stránky
        shot = (((entry["scan"] or {}).get("proposal") or {}).get("captures") or {}).get("page")
        if shot:
            captures.append({"label": entry["page"]["name"],
                             "url": f"/api/page-plan/scan/{entry['scan']['scanId']}/capture/{quote(shot)}?{scope}"})
    if scan:
        shots = (scan.get("proposal") or {}).get("captures") or {}
        node = _element(facts)
        section = (node.get("card") or {}).get("section") if "element" in node else None
        names = {item["id"]: item.get("name") or item["id"] for item in page["site"].get("sections") or []}
        base = f"/api/page-plan/scan/{scan['scanId']}/capture/"
        if shots.get("page") and section is None:
            captures.append({"label": page["name"], "url": base + quote(shots["page"]) + "?" + scope})
        captures += [{"label": names.get(key, key), "url": base + quote(name) + "?" + scope}
                     for key, name in (shots.get("sections") or {}).items() if section in (None, key)]
    if not captures and not preview:
        return None
    source = (f"/api/page-plan/scan/latest?{scope}&{urlencode({'pageId': page['id']})}" if page
              else f"/api/page-plan/scan/latest?{scope}&pageId={{pageId}}" if facts.get("domain")
              else "/api/pletor/linie/trace")
    return {"source": source, "captures": captures,
            "preview": {"url": preview.get("url"), "status": preview.get("state")} if preview else None}


def _linie_section(linie, project, workspace, trail_pr):
    if linie is None:
        return None
    ticket, shown, traced = linie["ticket"], linie["shown"], linie["trace"]
    mark = ticket["work"]["mark"]
    axes = [{"name": name, "state": axis.get("state") or ("deployed" if axis.get("envs") else "none"),
             "text": axis.get("src") or ((axis.get("sha") or "")[:7] or None)} for name, axis in shown["axes"].items()]
    pr = traced.get("pr") or trail_pr
    return {"source": f"/api/pletor/linie/trace/{mark}?{urlencode({'project': project, 'workspace': workspace})}",
            "ticketId": ticket["ticketId"], "mark": mark, "branch": ticket["work"].get("branch"),
            "pr": {"number": pr.get("number"), "state": pr.get("state")} if pr else None, "axes": axes,
            "commits": [{"sha7": item["sha7"], "title": item["title"]} for item in traced["commits"]],
            "gaps": [item["text"] for item in traced["gaps"]]}


def _runs(trail, costs):
    found = []
    for run in trail["runs"]:
        checks = [check for step in run["steps"] for check in step["checks"]]
        found.append({"executionId": run["executionId"], "at": run["createdAt"], "state": run["state"],
                      "tests": {"passed": sum(item["status"] == "green" for item in checks), "total": len(checks)}
                      if checks else None,
                      "costUsd": costs.get(run["executionId"]) if run["executionId"] else None})
    return found


def _agent(facts, mark, q, lease, revision):
    project, workspace, node = facts["project"], facts["workspace"], facts["nodeId"]
    scope = urlencode({"project": project, "workspace": workspace})
    reads = [{"layer": "souhrn", "method": "GET", "url": f"/api/desktop-v3/node-brief?{q}&layer=souhrn", "size": 40, "exists": True},
             {"layer": "tvar", "method": "GET", "url": f"/api/desktop-v3/node-brief?{q}&layer=tvar", "size": 700, "exists": True},
             {"layer": "proces", "method": "GET", "url": f"/api/oporahub/card-trail?{_query(project, workspace, node, 'node')}",
              "size": None, "exists": True},
             {"layer": "denik", "method": "SSE", "url": f"/api/oporahub/events/stream?{q}", "size": None, "exists": True},
             {"layer": "karta", "method": "GET", "url": f"/api/oporahub/live-card?{q}", "size": None, "exists": True},
             {"layer": "zadani", "method": "GET", "url": f"/api/desktop-v3/node-brief?{q}", "size": None, "exists": True},
             {"layer": "folie", "method": "GET", "url": f"/api/oporahub/plan-reality?{q}", "size": None, "exists": True}]
    if mark:
        reads.insert(5, {"layer": "linie", "method": "GET", "url": f"/api/pletor/linie/trace/{mark}?{scope}",
                         "size": None, "exists": True})
    writes = [{"role": "worker", "method": "POST", "url": "/api/oporahub/executions/claim", "what": "převzetí karty (lease)"},
              {"role": "worker", "method": "POST", "url": "/api/oporahub/executions/{executionId}/steps", "what": "průběžný krok"},
              {"role": "worker", "method": "POST", "url": "/api/oporahub/executions/{executionId}/results", "what": "výsledek běhu"},
              {"role": "agent", "method": "POST", "url": "/api/desktop-v3/agent-output", "what": "výstup agenta pod CAS revizí"},
              {"role": "agent", "method": "POST", "url": "/api/desktop-v3/agent-messages", "what": "zpráva na vazbě"},
              {"role": "heart", "method": "POST", "url": "/api/gate/requests", "what": "zápis srdce branou"},
              {"role": "heart", "method": "POST", "url": "/api/gate/requests",
               "what": "ticket.direct: pokyn běžícímu dělníkovi (hint, course, stop)"},
              {"role": "office", "method": "POST", "url": "/api/oporahub/process-events", "what": "události procesu z Kanceláře"}]
    return {"address": f"opora://card/{mark or node}", "lease": lease, "revision": revision, "reads": reads,
            "writes": writes, "triggers": [{"when": TRIGGER_WHEN[kind], "then": f"{kind} → budí srdce (cardTrigger)"}
                                           for kind in triggers.CARD_KINDS]}


def _page_child(entry, fallback):
    """Stránka domény podle plánu stránky: postup = podíl prvků logiky s potvrzeným uzavřením; všechny = leaf,
    některé = bud, žádné nebo stránka bez prvků = stav karty stránky."""
    total, done = entry["elements"], entry["done"]
    state = "leaf" if total and done == total else "bud" if done else fallback
    return {"nodeId": entry["page"]["id"], "title": entry["page"]["name"], "state": state,
            "progress": round(100 * done / total) if total else None}


def _children(node_id, graph, domain, states, sync):
    """Stránky domény (plátno 2) první, pak ostatní přímí potomci uzlu."""
    pages = [_page_child(entry, states[entry["page"]["id"]]) for entry in domain or []]
    shown = {item["nodeId"] for item in pages}
    return pages + [{"nodeId": child["id"], "title": child["name"], "state": states[child["id"]],
                     "progress": progress_of(sync.get(child["id"]))}
                    for child in graph["nodes"] if child.get("parentId") == node_id and child["id"] not in shown]


def compose(facts):
    """Čistá projekce faktů `gather` do tvaru kontraktu K1."""
    project, workspace, node_id, trail_facts = facts["project"], facts["workspace"], facts["nodeId"], facts["trail"]
    trail = card_trail.project_trail(trail_facts)
    graph, brief, sync, linie = facts["graph"], facts["brief"], facts["sync"], facts["linie"]
    node = next(item for item in graph["nodes"] if item["id"] == node_id)
    names = {item["id"]: item.get("name") or item["id"] for item in graph["nodes"]}
    q = _query(project, workspace, node_id)
    merged = (trail["pr"] or {}).get("state") == "merged"
    dry = bool(((linie or {}).get("ticket") or {}).get("work", {}).get("blocked"))
    state = state_of(node, sync.get(node_id), merged=merged, held=trail["now"] is not None, dry=dry)
    states = {item["id"]: state_of(item, sync.get(item["id"])) for item in graph["nodes"]} | {node_id: state}
    item = sync.get(node_id) or {}
    events = card_trail.recent(trail_facts.get("events") or [], trail_facts.get("activity") or [], RECENT)
    recent = [{"at": entry["at"], "actor": entry["who"], "kind": entry["kind"], "text": entry["label"],
               "source": entry["source"]} for entry in events]
    # OP-3DAFF9.3: poslední zásah srdce = nejnovější `ticket.direct` se severity (zpětná vazba ticketů karty je trvalá,
    # událost `worker.message` z okna 200 událostí karty rychle vypadne), jinak zápis srdce v deníku
    directs = [{"at": item["createdAt"], "severity": item["kind"].split(".", 1)[1], "text": item["text"]}
               for ticket in trail_facts.get("tickets") or [] for item in ticket.get("feedback") or []
               if item["kind"].startswith("heart.")]
    directs += [{"at": event["at"], "severity": event["data"].get("severity"), "text": event["data"].get("text")}
                for event in trail_facts.get("events") or [] if event.get("kind") == "worker.message"]
    heart = max(directs, key=lambda item: card_trail.moment(item["at"]), default=None) or next(
        ({"at": entry["at"], "severity": None, "text": entry["text"]} for entry in recent
         if card_trail.author(entry["actor"]) == "heart"), None)
    costs = facts["costs"]
    runs = _runs(trail, costs["executions"])
    mark = ((linie or {}).get("ticket") or {}).get("work", {}).get("mark")
    executions = {run["executionId"] for run in runs}
    decisions = [{"text": entry["title"], "source": "/api/oporahub/agent-state"}
                 for entry in facts["decisions"] if entry.get("targetId") in executions | {node_id}]
    decisions += [{"text": entry.get("text"), "source": f"/api/desktop-v3/node-brief?{q}"}
                  for entry in brief["context"]["decisions"] if entry.get("text")]
    gauge = (facts["agent"] or {}).get("gauge") or {}
    pills = [{"text": item["nextAction"]["label"], "tone": "work"}] if item.get("nextAction") else []
    if trail["pr"]:
        pills.append({"text": f"PR #{trail['pr']['number']} {trail['pr']['state']}", "tone": "real"})
    if mark:
        pills.append({"text": mark, "tone": "work"})
    if (gauge.get("risk") or {}).get("level") in ("elevated", "critical"):
        pills.append({"text": f"riziko {gauge['risk']['level']}", "tone": "risk"})
    pills += [{"text": flag["code"], "tone": "risk"} for flag in trail["judgment"]]
    if heart:
        pills.append({"text": "srdce", "tone": "heart"})
    request = brief["outputContract"]["request"]
    lease = {"holder": trail["now"]["owner"], "until": trail["now"]["until"]} if trail["now"] else None
    return {
        "nodeId": node_id, "title": node["name"], "kind": node["kind"], "crumbs": brief["node"]["path"],
        "state": state, "progress": progress_of(item), "pills": pills,
        "truths": {"vision": _vision(brief | {"acceptanceEvidence": item.get("acceptanceEvidence")}, q, state == "leaf"),
                   "mirror": _mirror(facts.get("mirror"), q),
                   "reality": _reality(trail_facts.get("done"), _query(project, workspace, node_id, "node"), linie),
                   "future": _future(facts.get("future"))},
        "edges": _edges(node_id, graph, trail_facts.get("reports") or {}, states, names),
        "flow": _flow(facts, q), "output": _output(facts, linie),
        "linie": _linie_section(linie, project, workspace, trail["pr"]),
        "runs": runs,
        "cost": {"totalUsd": costs["nodes"].get(node_id), "budgetUsd": None},
        "recent": recent, "decisions": decisions,
        "children": _children(node_id, graph, facts.get("domain"), states, sync),
        "next": {"text": item["nextAction"]["label"], "why": item["nextAction"]["reason"]} if item.get("nextAction") else None,
        "heart": heart,
        "agent": _agent(facts, mark, q, lease, request["expectedRevision"] if request else None),
    }


def layer(facts, name):
    """Vrstva node-briefu: `souhrn` (≈ 40 tok) nebo `tvar` (≈ 700 tok) ze stejné živé karty (`compose`).
    `blocked` = důvod blokace ProcessSync, jinak ruční blokace Linie, jinak None."""
    if name not in LAYERS:
        raise ValueError(f"Neznámá vrstva {name!r}; platí {', '.join(LAYERS)}.")
    card = compose(facts)
    if name == "souhrn":
        item = facts["sync"].get(facts["nodeId"]) or {}
        held = ((facts["linie"] or {}).get("ticket") or {}).get("work", {}).get("blocked")
        blocked = (item["nextAction"]["reason"] if item.get("status") == "blocked"
                   else (held.get("reason") or "blokováno v Linii") if held else None)
        truths = {key: None if not value or "items" not in value else
                  {"ok": sum(item["status"] == "ok" for item in value["items"]), "total": len(value["items"])}
                  for key, value in card["truths"].items()}
        return {"id": card["nodeId"], "title": card["title"], "state": card["state"], "progress": card["progress"],
                "next": (card["next"] or {}).get("text"), "blocked": blocked,
                "truths": truths}
    return {"criteria": (card["truths"]["vision"] or {}).get("items", []), "edges": card["edges"],
            "children": card["children"]}
