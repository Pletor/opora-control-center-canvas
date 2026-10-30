"""Výslech srdce, vrstva determinismu (docs/navrhy/2026-10-30-vyslech-srdce.md, řez 1), bez modelu.

- `needs_brief` je tabulka §2: kdy se výslech spustí (nový požadavek `fix_for_milestone`, otevřené rozšíření
  `later_extension`, `changes_intent` na dopady, karta `ready` s měřákem `evidence: thin` krátce, člověk klikne
  ve Velínu „Vyslechni mě k tomu“ = `asked`, řez 3).
- `situation` složí spis požadavku (§3.1): vstupy doslova a podobné vstupy, ZÁMĚR, oblast, milník s kritérii,
  související karty se štítkem měřáku (`card_gauge`), pravidla a rozhodnutí. `collect_situation` fakta přečte.
- `clarity` je kontrola kritérií jasna (§4); stav `clear` nastaví jen `save_synthesis`, když nic nechybí.
- `save_synthesis` / `ask` jsou příkazy srdce `brief` a `ask` (§7): syntéza a nejvýš 3 otevřené otázky
  s doporučenou odpovědí, nejvýš 3 kola.
- `answer` / `start` jsou kanál člověka z Velínu (řez 3, `POST /api/intake/brief/answer` a `/brief/start`, routa
  pouští jen `require_authority`): odpověď nebo potvrzené doporučení se zapíše do `questions[].answer` /
  `answered_at` (ne do `intake_entries`, §10.3); „Vyslechni mě k tomu“ založí spis `draft` se značkou `askedAt`.
  `human_wakes` / `fire_human` z toho udělají vstup dávky jednou na odpověď (`trigger:brief:<rq>:answer:<q>`)
  a jednou na žádost (`trigger:brief:<rq>:asked`).
- `requirement_wakes` / `card_hit` jsou spouštěč výslechu: jednou na stav (`heart_triggers`, klíč
  `trigger:brief:<rq>:<důvod>` a `trigger:brief:card:<uzel>:thin@<prostor>`). Vypnutý výslech
  (`settings.brain.brief.enabled`, `brief_setting.py`, řez 2) nebudí nic.
- `research_budget` / `research_spend` hlídají strop ceny rešerše na požadavek (§8, `brief_setting.researchUsd`):
  cena se sčítá do `intake_briefs.cost_usd`, po vyčerpání `research --requirement` odmítne (409).
"""
import json
import sqlite3

from backend.brain_opora.determinism import brief_setting
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas import card_gauge
from backend.canvas.graph import valid_id
from database.repositories.heart_triggers import HeartTriggers
from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements

STATUSES = ("draft", "research", "grilling", "clear")
ORIGINS = ("human", "research", "derived")  # člověk, rešerše (odkaz na zdroj), odvozeno (z čeho)
CHECKS = ("test", "measure", "observe")  # kritérium přijetí je ověřitelné testem, měřením nebo pozorováním
IMPACTS = ("high", "medium", "low")
ACCEPTANCE, OPEN_QUESTIONS, ROUNDS = 3, 3, 3
TEXT, QUESTION, WHY, SYNTHESIS = 300, 500, 300, 20000  # znaků textu položky, otázky, důvodu, celé syntézy (JSON)
CARDS, RULES, SIMILAR = 20, 10, 3  # nejvýš karet, pravidel/rozhodnutí a podobných vstupů ve spisu
WINDOW_HOURS = 24  # spouštěč požadavku jen s vstupem novějším než tolik hodin (staré požadavky se nevyslýchají)
REASONS = {"new": "nový požadavek", "opened": "otevřené rozšíření", "changes_intent": "mění záměr, vyslechni dopady",
           "thin": "karta k předání má málo podkladů, doplň kroky a soubory",
           "asked": "člověk ve Velínu požádal o výslech",
           "answer": "odpověď člověka na výslech, uprav syntézu (brief), polož další otázku, nebo rozhodni"}
MISSING = {"goal": "goal: cíl jednou větou", "users": "users: pro koho",
           "acceptance": f"acceptance: aspoň {ACCEPTANCE} kritéria s check test|measure|observe",
           "outOfScope": "outOfScope: hranice, co ne",
           "parts": "parts: úplný seznam částí s origin",
           "parts.origin": "parts: aspoň jedna položka origin research|derived se source",
           "dependencies": "dependencies: závislosti na kartách nebo oblastech (žádná = {ref: none, text: proč})",
           "questions.high": "questions: otevřená otázka s impact high",
           "questions.open": "otázky výslechu čekají na odpověď člověka"}
SHAPE = ('{"goal": "…", "users": "…", "parts": [{"text": "…", "origin": "human|research|derived", "source": "…"}], '
         '"acceptance": [{"text": "…", "check": "test|measure|observe"}], "outOfScope": ["…"], '
         '"assumptions": ["…"], "risks": ["…"], "dependencies": [{"ref": "nodeId|areaId|none", "text": "…"}], '
         '"questions": [{"text": "…", "impact": "high|medium|low", "answer": "…"}]}')
HINT = "python opora_heart.py brief --requirement rq_… --synthesis @dilna/out/brief.json; tvar: " + SHAPE
ASK_HINT = 'python opora_heart.py ask --requirement rq_… --question "…" --recommended "…" --why "…"'
SPENT_HINT = "strop rešerše vyčerpán, rozhodni z toho, co máš"
SOURCES = 6  # nejvýš ověřených zdrojů jedné rešerše ve spisu


def needs_brief(*, status, verdicts=(), brief_status=None, evidence=None, enabled=True, asked=False):
    """Důvod výslechu podle tabulky §2, nebo None; vypnutý výslech (`enabled` False) nikdy.
    Karta (`evidence` není None): `ready` + `thin` → `thin`.
    Člověk ve Velínu klikl „Vyslechni mě k tomu“ (`asked`): požadavek `open` nebo `deferred` → `asked`.
    Požadavek: jen `open`; `changes_intent` mezi vstupy → `changes_intent` (i po jasnu, na dopady); s jasnem
    nic; zakládající vstup (první) `fix_for_milestone` → `new`, `later_extension` (už otevřený) → `opened`;
    `duplicate`, `done`, `extends_in_progress` a ostatní nic."""
    if not enabled:
        return None
    if evidence is not None:
        return "thin" if status == "ready" and evidence == "thin" else None
    if asked:
        return "asked" if status in ("open", "deferred") else None
    if status != "open" or not verdicts:
        return None
    if "changes_intent" in verdicts:
        return "changes_intent"
    if brief_status == "clear":
        return None
    return {"fix_for_milestone": "new", "later_extension": "opened"}.get(verdicts[0])


def _texts(value):
    return [item for item in value or [] if isinstance(item, str) and item.strip()]


def _sourced(part):
    return part.get("origin") in ("research", "derived") and bool(str(part.get("source") or "").strip())


def clarity(synthesis, questions=()):
    """Co chybí do jasna (§4), jako `MISSING` texty v pevném pořadí; prázdný seznam = `clear`.
    `questions` = otázky výslechu (`ask`): bez odpovědi brání jasnu."""
    synthesis = synthesis if isinstance(synthesis, dict) else {}
    parts = [part for part in synthesis.get("parts") or [] if isinstance(part, dict)]
    acceptance = [item for item in synthesis.get("acceptance") or []
                  if isinstance(item, dict) and str(item.get("text") or "").strip() and item.get("check") in CHECKS]
    found = []
    for key in ("goal", "users"):
        if not str(synthesis.get(key) or "").strip():
            found.append(key)
    if len(acceptance) < ACCEPTANCE:
        found.append("acceptance")
    if not _texts(synthesis.get("outOfScope")):
        found.append("outOfScope")
    if not parts:
        found.append("parts")
    elif not any(_sourced(part) for part in parts):
        found.append("parts.origin")
    if not [item for item in synthesis.get("dependencies") or [] if isinstance(item, dict) and item.get("ref")]:
        found.append("dependencies")
    if any(isinstance(item, dict) and item.get("impact") == "high" and not str(item.get("answer") or "").strip()
           for item in synthesis.get("questions") or []):
        found.append("questions.high")
    if any(item.get("answer") is None for item in questions or [] if isinstance(item, dict)):
        found.append("questions.open")
    return [MISSING[key] for key in found]


def check_synthesis(synthesis):
    """Tvar syntézy (ne úplnost, tu měří `clarity`): objekt známých klíčů, správné typy a hodnoty výčtů."""
    if not isinstance(synthesis, dict) or not synthesis:
        raise invalid("Syntéza je neprázdný JSON objekt.", HINT)
    unknown = set(synthesis) - {"goal", "users", "parts", "acceptance", "outOfScope", "assumptions", "risks",
                                "dependencies", "questions"}
    if unknown:
        raise invalid(f"Neznámé klíče syntézy: {', '.join(sorted(unknown))}.", HINT)
    if len(json.dumps(synthesis, ensure_ascii=False)) > SYNTHESIS:
        raise invalid(f"Syntéza je delší než {SYNTHESIS} znaků.", "Zkrať texty; seznam částí ponech úplný.")
    lists = {"parts": ("text", "origin"), "acceptance": ("text", "check"), "dependencies": ("ref", "text"),
             "questions": ("text", "impact")}
    for key in ("goal", "users"):
        if key in synthesis and not isinstance(synthesis[key], str):
            raise invalid(f"{key} je text.", HINT)
    for key in ("outOfScope", "assumptions", "risks"):
        if key in synthesis and not (isinstance(synthesis[key], list)
                                     and all(isinstance(item, str) for item in synthesis[key])):
            raise invalid(f"{key} je seznam textů.", HINT)
    for key, required in lists.items():
        items = synthesis.get(key, [])
        if not isinstance(items, list) or not all(isinstance(item, dict) and all(
                isinstance(item.get(name), str) and item[name].strip() for name in required) for item in items):
            raise invalid(f"{key} je seznam objektů s {', '.join(required)}.", HINT)
    enums = (("parts", "origin", ORIGINS), ("acceptance", "check", CHECKS), ("questions", "impact", IMPACTS))
    for key, name, allowed in enums:
        if any(item[name] not in allowed for item in synthesis.get(key, [])):
            raise invalid(f"{key}[].{name} je jedno z: {', '.join(allowed)}.", HINT)
    return synthesis


def _short(value, limit=TEXT):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def situation(requirement, entries, similar, intent, area, milestone, cards, rules, decisions):
    """Spis požadavku (§3.1) z hotových faktů: vstupy doslova, podobné vstupy, ZÁMĚR, oblast, milník s kritérii,
    související karty se štítkem měřáku, pravidla a rozhodnutí. Čistá funkce, délky se zkrátí."""
    return {"requirement": {key: requirement.get(key) for key in ("id", "title", "status")},
            "inputs": [{"id": item["id"], "text": item["text"], "verdict": item.get("verdict")} for item in entries],
            "similar": [{"id": item["id"], "text": _short(item.get("text"))} for item in similar[:SIMILAR]],
            "intent": _short(intent, 400),
            "area": area,
            "milestone": None if milestone is None else {
                "id": milestone["id"], "title": milestone["title"], "status": milestone.get("status"),
                "criteria": [_short(item.get("text")) for item in milestone.get("criteria") or []]},
            "cards": cards[:CARDS],
            "rules": [_short(item) for item in rules[:RULES]],
            "decisions": [_short(item) for item in decisions[:RULES]]}


def summary(spis, limit=600):
    """Jeden řádek spisu do dávky srdce: vstup doslova, oblast, milník a karty se štítky."""
    parts = [f"„{_short(spis['inputs'][0]['text'], 200)}“" if spis.get("inputs") else "bez vstupu"]
    if spis.get("area"):
        parts.append(f"oblast {spis['area']['id']} „{spis['area']['name']}“")
    if spis.get("milestone"):
        parts.append(f"milník {spis['milestone']['id']} „{spis['milestone']['title']}“")
    cards = spis.get("cards") or []
    parts.append("karty: " + (", ".join(f"{card['id']} [{card['label']}]" for card in cards[:8]) or "žádné"))
    return _short(" · ".join(parts), limit)


def _cards(service, project, workspace, area, milestone):
    """Karty oblasti (přímo, nebo přes sektor) a karty kritérií milníku se štítkem měřáku; nečitelné = žádné."""
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_plan_steps import steps_of

    try:
        graph = service.view(project, workspace)["graph"]
        accepted = {item["nodeId"]: item for item in OporaChangesets(service).context(project, workspace)["acceptedDocuments"]}
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
        return []
    index = card_gauge.graph_index(graph)
    nodes = index["nodes"]
    criteria = {card for item in (milestone or {}).get("criteria") or [] for card in item.get("cards") or []}

    def member(node):
        owner = nodes.get(node.get("parentId")) or {}
        return area is not None and area in (node.get("memberOf"), owner.get("memberOf"))

    found = []
    for node in nodes.values():
        if node.get("kind") not in card_gauge.CARD_KINDS or not (member(node) or node["id"] in criteria):
            continue
        steps = steps_of((accepted.get(node["id"]) or {}).get("fields"))
        run = card_gauge.profile(node, graph, steps, index)
        found.append({"id": node["id"], "name": _short(node.get("name") or node["id"], 120), "label": run["label"],
                      "evidence": run["evidence"], "steps": len(steps or [])})
    return found[:CARDS]


def collect_situation(service, project, workspace, requirement_id):
    """Spis požadavku z databáze, grafu a paměti projektu (čte, nic nezapisuje). Neznámý požadavek = None."""
    from backend.brain_opora.determinism import intake, snapshot

    with service.reading(project):
        db = service.db_for(project)
        requirement = IntakeRequirements(db).get(requirement_id)
        if requirement is None or requirement["workspaceId"] != workspace:
            return None
        entries = IntakeBriefs(db).entries_of(requirement_id)
        found = intake.candidates(db, {**entries[0], "workspaceId": workspace}, SIMILAR) if entries else []
        similar = [entry for entry in (IntakeEntries(db).get(item) for item in found) if entry]
        milestones = IntakeMilestones(db)
        milestone = milestones.get(requirement["milestoneId"]) if requirement.get("milestoneId") else None
        if milestone is None and requirement.get("areaId"):
            milestone = milestones.active(workspace, requirement["areaId"])
    _, goal = snapshot._identity(service, project)
    rules, decisions = snapshot._memory(service, project, workspace)
    areas = {item["id"]: item for item in intake.areas(service, project, workspace)}
    area = areas.get(requirement.get("areaId")) if requirement.get("areaId") else None
    return situation(requirement, entries, similar, goal, area, milestone,
                     _cards(service, project, workspace, requirement.get("areaId"), milestone),
                     [rule.get("text") for rule in rules], [item.get("text") for item in decisions])


def view(brief):
    """`brief` požadavku v `GET /api/intake`: `{status, synthesis, questions, missing}`, bez spisu None.
    Syntézu (cíl, části s původem, kritéria, hranice) čte panel výslechu ve Velínu (řez 3)."""
    if brief is None:
        return None
    return {"status": brief["status"], "synthesis": brief["synthesis"], "questions": brief["questions"],
            "missing": clarity(brief["synthesis"], brief["questions"])}


def _requirement(db, workspace, requirement_id):
    requirement = IntakeRequirements(db).get(requirement_id) if isinstance(requirement_id, str) else None
    if requirement is None or requirement["workspaceId"] != workspace:
        raise GateError(404, "intake_requirement_not_found", "Požadavek v tomto pracovním prostoru neexistuje.",
                        "ID požadavku (rq_…) je v řádku VÝSLECH dávky nebo v sekci POŽADAVKY snímku.")
    return requirement


def _status(missing, questions, current):
    if not missing:
        return "clear"
    if any(item.get("answer") is None for item in questions):
        return "grilling"
    return current if current in ("research", "grilling") else "draft"


def save_synthesis(service, session, requirement_id, synthesis, now):
    """Příkaz `brief` (§7): uloží syntézu požadavku svého prostoru a obnoví spis. `clear` jen bez `missing`."""
    check_synthesis(synthesis)
    project, workspace = session["project_id"], session["workspace_id"]
    with service.reading(project):
        _requirement(service.db_for(project), workspace, requirement_id)
    spis = collect_situation(service, project, workspace, requirement_id)
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            _requirement(db, workspace, requirement_id)
            store = IntakeBriefs(db)
            brief = store.get(requirement_id) or {"requirementId": requirement_id, "workspaceId": workspace,
                                                   "status": "draft", "questions": [], "rounds": 0}
            missing = clarity(synthesis, brief["questions"])
            status = _status(missing, brief["questions"], brief["status"])
            store.save({**brief, "situation": spis or brief.get("situation") or {}, "synthesis": synthesis,
                        "status": status, "updatedAt": now})
    return {"requirement": requirement_id, "status": status, "missing": missing}


def _text(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise invalid(f"{name} je neprázdný text do {limit} znaků.", ASK_HINT)
    return value.strip()


def ask(service, session, requirement_id, question, recommended, why, now):
    """Příkaz `ask` (§3.4): otázka výslechu s doporučenou odpovědí a důvodem. Nejvýš `OPEN_QUESTIONS` otevřených;
    otázka bez otevřených začíná nové kolo, nejvýš `ROUNDS` kol. Spis musí mít syntézu (nejdřív `brief`)."""
    item = {"text": _text(question, QUESTION, "question"), "recommended": _text(recommended, QUESTION, "recommended"),
            "why": _text(why, WHY, "why"), "answer": None, "answered_at": None}
    project, workspace = session["project_id"], session["workspace_id"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            _requirement(db, workspace, requirement_id)
            store = IntakeBriefs(db)
            brief = store.get(requirement_id)
            if brief is None or brief["synthesis"] is None:
                raise GateError(409, "brief_missing", "Požadavek ještě nemá syntézu.",
                                "Nejdřív ulož syntézu: " + HINT)
            questions = list(brief["questions"])
            waiting = [entry for entry in questions if entry.get("answer") is None]
            if len(waiting) >= OPEN_QUESTIONS:
                raise GateError(409, "brief_questions_full", f"Otevřené jsou už {OPEN_QUESTIONS} otázky.",
                                "Počkej na odpověď člověka; další otázku polož v příští dávce.")
            rounds = brief["rounds"]
            if not waiting:
                if rounds >= ROUNDS:
                    raise GateError(409, "brief_rounds_spent", f"Výslech už měl {ROUNDS} kola.",
                                    "Rozhodni sám a nejasnosti zapiš do assumptions syntézy (brief).")
                rounds += 1
            questions.append({"id": f"q{len(questions) + 1}", **item})
            missing = clarity(brief["synthesis"], questions)
            store.save({**brief, "questions": questions, "rounds": rounds, "status": "grilling", "updatedAt": now})
    return {"requirement": requirement_id, "status": "grilling", "question": questions[-1]["id"],
            "open": len(waiting) + 1, "rounds": rounds, "missing": missing}


def requirement_key(requirement_id, reason):
    return f"trigger:brief:{requirement_id}:{reason}"


def card_key(node, workspace):
    return f"trigger:brief:card:{node}:thin@{workspace}"


def requirement_wakes(db, since, enabled=True):
    """Kandidáti výslechu `[(prostor, požadavek, důvod)]`: otevřené požadavky se vstupem novějším než `since`
    (ISO čas), kterým `needs_brief` dá důvod a srdce na ten stav ještě nebudilo. Jen čte; vypnuto = nic."""
    if not enabled:
        return []
    rows = db.execute("SELECT DISTINCT workspace_id FROM intake_requirements WHERE status='open'"
                      " ORDER BY workspace_id").fetchall()
    briefs, triggers, found = IntakeBriefs(db), HeartTriggers(db), []
    for (workspace,) in rows:
        for requirement in IntakeRequirements(db).list(workspace, ("open",)):
            entries = briefs.entries_of(requirement["id"])
            if not entries or max(str(item["createdAt"]) for item in entries) < since:
                continue
            brief = briefs.get(requirement["id"])
            reason = needs_brief(status=requirement["status"], verdicts=[item["verdict"] for item in entries],
                                 brief_status=brief["status"] if brief else None, enabled=enabled)
            if reason and not triggers.fired(requirement_key(requirement["id"], reason)):
                found.append((workspace, requirement, reason))
    return found


def open_brief(db, workspace, requirement, reason, spis, at):
    """Pod zámkem volajícího: značka „už jsem budil“ a spis (`draft`, jasný spis se kvůli `changes_intent` vrátí
    do `draft`). Vrací vstup dávky `brief`, nebo None (značka už byla)."""
    if not HeartTriggers(db).fire(requirement_key(requirement["id"], reason), workspace, at):
        return None
    store = IntakeBriefs(db)
    brief = store.get(requirement["id"]) or {"requirementId": requirement["id"], "workspaceId": workspace,
                                             "status": "draft", "questions": [], "rounds": 0}
    status = "draft" if brief["status"] == "clear" else brief["status"]
    store.save({**brief, "situation": spis or brief.get("situation") or {}, "status": status, "updatedAt": at})
    return {"type": "brief", "requirementId": requirement["id"], "title": requirement["title"], "reason": reason,
            "detail": summary(spis) if spis else ""}


def card_hit(card, enabled=True):
    """Spouštěč krátkého výslechu karty (`triggers.wakes`, `extra`): `(klíč, vstup brief)`, nebo None."""
    if needs_brief(status=card.get("status"), evidence=card.get("evidence"), enabled=enabled) != "thin":
        return None
    return card_key(card["nodeId"], card.get("workspace")), {
        "type": "brief", "nodeId": card["nodeId"], "title": card.get("title") or card["nodeId"], "reason": "thin",
        "detail": card_gauge.THIN_REASON}


def _spent(brief):
    return round(float((brief or {}).get("costUsd") or 0), 6)


def research_budget(service, session, requirement_id):
    """Strop rešerše požadavku (§8) před `research --requirement`: `{requirement, spentUsd, capUsd, leftUsd}`;
    vyčerpaný strop = 409 `brief_research_spent` s hintem `SPENT_HINT`. Jen čte."""
    project, workspace = session["project_id"], session["workspace_id"]
    cap = brief_setting.read(service, project)["researchUsd"]
    with service.reading(project):
        db = service.db_for(project)
        _requirement(db, workspace, requirement_id)
        spent = _spent(IntakeBriefs(db).get(requirement_id))
    if spent >= cap:
        raise GateError(409, "brief_research_spent",
                        f"Rešerše požadavku stála {spent:.2f} USD, strop je {cap:.2f} USD.", SPENT_HINT)
    return {"requirement": requirement_id, "spentUsd": spent, "capUsd": cap, "leftUsd": round(cap - spent, 6)}


def _sources(value):
    found = [item.strip()[:2048] for item in value if isinstance(item, str) and item.strip()] if isinstance(
        value, list) else []
    return list(dict.fromkeys(found))[:SOURCES]


def research_spend(service, session, requirement_id, cost, fragment=None, digest="", sources=(), now=None):
    """Po `research --requirement`: cena se přičte do `intake_briefs.cost_usd` a výsledek (fragment schránky,
    výtah, ověřené zdroje) do `research`. Spis bez syntézy se přepne do `research`. Vrací stav stropu."""
    if type(cost) not in (int, float) or not 0 <= cost <= 100:
        raise invalid("costUsd je číslo 0–100.", "Cenu vrací výtah rešerše (`costUsd`).")
    project, workspace = session["project_id"], session["workspace_id"]
    cap = brief_setting.read(service, project)["researchUsd"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            _requirement(db, workspace, requirement_id)
            store = IntakeBriefs(db)
            brief = store.get(requirement_id) or {"requirementId": requirement_id, "workspaceId": workspace,
                                                   "status": "draft", "questions": [], "rounds": 0}
            spent = round(_spent(brief) + cost, 6)
            research = [*(brief.get("research") or []),
                        {"fragmentId": fragment if isinstance(fragment, str) else None,
                         "digest": _short(digest, TEXT), "sources": _sources(list(sources or [])),
                         "costUsd": round(float(cost), 6), "at": now}]
            status = "research" if brief["status"] == "draft" and brief.get("synthesis") is None else brief["status"]
            store.save({**brief, "research": research, "costUsd": spent, "status": status, "updatedAt": now})
    return {"requirement": requirement_id, "spentUsd": spent, "capUsd": cap, "leftUsd": round(max(cap - spent, 0), 6)}


ANSWER_HINT = ('{"project": "<id>", "workspace": "main", "requirement": "rq_…", "question": "q1", "accept": true}'
               ' nebo místo accept "answer": "text odpovědi"')
START_HINT = '{"project": "<id>", "workspace": "main", "requirement": "rq_…"}'


def _scope(service, payload, keys, optional, hint):
    """Tělo kanálu člověka: přesně `keys` (+ volitelné), existující projekt a platný prostor."""
    if not isinstance(payload, dict) or not set(keys) <= set(payload) or set(payload) - set(keys) - set(optional):
        raise invalid(f"Tělo je {{{', '.join(keys)}}}" + (f" a jedno z {', '.join(optional)}." if optional else "."),
                      hint)
    project, workspace = payload["project"], payload["workspace"]
    if not isinstance(project, str) or not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if not isinstance(workspace, str) or not valid_id(workspace):
        raise invalid("Neplatný pracovní prostor.", "Použijte main, draft nebo ID pracovního prostoru.")
    return project, workspace


def _answer_text(payload):
    """`(odpověď, potvrzeno)`: vlastní text, nebo `accept: true` (doporučení srdce, text doplní volající)."""
    if ("answer" in payload) == ("accept" in payload) or ("accept" in payload and payload["accept"] is not True):
        raise invalid("Pošli buď answer (text odpovědi), nebo accept: true (potvrzení doporučení).", ANSWER_HINT)
    if "accept" in payload:
        return None, True
    text = payload["answer"]
    if not isinstance(text, str) or not text.strip() or len(text) > QUESTION or "\0" in text:
        raise invalid(f"answer je neprázdný text do {QUESTION} znaků.", ANSWER_HINT)
    return text.strip(), False


def _open_question(brief, question_id):
    if brief is None:
        raise GateError(404, "brief_not_found", "Požadavek zatím nemá spis výslechu.",
                        "Výslech založí srdce, nebo člověk tlačítkem „Vyslechni mě k tomu“.")
    index = next((number for number, item in enumerate(brief["questions"])
                  if isinstance(item, dict) and item.get("id") == question_id), None)
    if index is None:
        raise GateError(404, "brief_question_not_found", "Otázka ve spisu požadavku není.",
                        "ID otázky (q1…) je v GET /api/intake u požadavku v brief.questions.")
    if brief["questions"][index].get("answer") is not None:
        raise GateError(409, "brief_question_answered", "Na otázku už je odpověď.",
                        "Další otázku položí srdce v příští dávce.")
    return index


def answer(service, payload, now):
    """Odpověď člověka na otázku výslechu (`POST /api/intake/brief/answer`, §3.4, řez 3): `answer` = vlastní text,
    `accept: true` = doporučená odpověď srdce. Zapíše `answer`, `answered_at` a `accepted` do otázky spisu; stav
    `clear` tu nevzniká (syntézu po odpovědi upraví srdce příkazem `brief`). Odpovědět jde jen jednou, jinak 409."""
    project, workspace = _scope(service, payload, ("project", "workspace", "requirement", "question"),
                                ("answer", "accept"), ANSWER_HINT)
    text, accepted = _answer_text(payload)
    requirement_id = payload["requirement"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            _requirement(db, workspace, requirement_id)
            store = IntakeBriefs(db)
            brief = store.get(requirement_id)
            index = _open_question(brief, payload["question"])
            questions = list(brief["questions"])
            item = questions[index]
            value = item["recommended"] if accepted else text
            questions[index] = {**item, "answer": value, "answered_at": now, "accepted": accepted}
            waiting = sum(1 for entry in questions if entry.get("answer") is None)
            status = "grilling" if waiting else brief["status"]
            missing = clarity(brief["synthesis"], questions)
            store.save({**brief, "questions": questions, "status": status, "updatedAt": now})
    return {"requirement": requirement_id, "question": payload["question"], "answer": value, "accepted": accepted,
            "status": status, "open": waiting, "missing": missing}


def start(service, payload, now):
    """„Vyslechni mě k tomu“ (§2, řez 3): založí spis požadavku ve stavu `draft` se spisem a značkou `askedAt`;
    srdce ho pak dostane jednou (`human_wakes`). Existující spis 409 `brief_exists`, vypnutý výslech 409."""
    project, workspace = _scope(service, payload, ("project", "workspace", "requirement"), (), START_HINT)
    if not brief_setting.read(service, project)["enabled"]:
        raise GateError(409, "brief_disabled", "Výslech je v nastavení projektu vypnutý.",
                        "Zapněte ho v nastavení mozku (brain.brief).")
    with service.reading(project):
        requirement = _requirement(service.db_for(project), workspace, payload["requirement"])
    if needs_brief(status=requirement["status"], asked=True) is None:
        raise GateError(409, "brief_requirement_closed", "Vyslechnout jde jen otevřený nebo odložený požadavek.",
                        "Požadavek je už vyřízený.")
    spis = collect_situation(service, project, workspace, requirement["id"]) or {}
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            _requirement(db, workspace, requirement["id"])
            store = IntakeBriefs(db)
            if store.get(requirement["id"]) is not None:
                raise GateError(409, "brief_exists", "Požadavek už spis výslechu má.",
                                "Otázky a syntéza jsou v GET /api/intake u požadavku.")
            store.save({"requirementId": requirement["id"], "workspaceId": workspace, "status": "draft",
                        "situation": {**spis, "askedAt": now}, "questions": [], "rounds": 0, "updatedAt": now})
    return {"requirement": requirement["id"], "status": "draft"}


def answer_key(requirement_id, question_id):
    return f"trigger:brief:{requirement_id}:answer:{question_id}"


def _answer_line(item):
    question = f"otázka {item.get('id')} „{_short(item.get('text'), 160)}“"
    if item.get("accepted"):
        return f"{question} → člověk potvrdil doporučení „{_short(item.get('answer'), 200)}“"
    return (f"{question} → člověk odpověděl „{_short(item.get('answer'), 200)}“"
            f" (doporučení bylo „{_short(item.get('recommended'), 120)}“)")


def human_wakes(db):
    """Kandidáti `[(prostor, klíč, vstup brief)]` z kanálu člověka, na které srdce ještě nebudilo: žádost
    „Vyslechni mě k tomu“ (`askedAt` ve spisu) a každá zodpovězená otázka. Jen čte. Nastavení `brain.brief` je
    nezastaví, protože jde o přímou akci člověka (vypnutý výslech novou žádost odmítne už `start`)."""
    triggers, requirements, found = HeartTriggers(db), IntakeRequirements(db), []
    rows = db.execute("SELECT DISTINCT workspace_id FROM intake_briefs ORDER BY workspace_id").fetchall()
    for (workspace,) in rows:
        for requirement_id, item in sorted(IntakeBriefs(db).of_workspace(workspace).items()):
            requirement = requirements.get(requirement_id)
            if requirement is None:
                continue
            base = {"type": "brief", "requirementId": requirement_id, "title": requirement["title"]}
            situation = item.get("situation") or {}
            key = requirement_key(requirement_id, "asked")
            if situation.get("askedAt") and not triggers.fired(key):
                detail = summary(situation) if situation.get("requirement") else ""
                found.append((workspace, key, {**base, "reason": "asked", "detail": detail}))
            for question in item["questions"]:
                if not isinstance(question, dict) or question.get("answer") is None:
                    continue
                key = answer_key(requirement_id, question.get("id"))
                if not triggers.fired(key):
                    found.append((workspace, key, {**base, "reason": "answer", "detail": _answer_line(question)}))
    return found


def fire_human(db, candidates, at):
    """Pod zámkem volajícího zapíše značky kandidátů `human_wakes`; vrací `[(prostor, vstup)]` jen poprvé zapsaných."""
    return [(workspace, item) for workspace, key, item in candidates if HeartTriggers(db).fire(key, workspace, at)]
