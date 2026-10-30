"""Výslech srdce, vrstva determinismu (docs/navrhy/2026-10-30-vyslech-srdce.md, řez 1), bez modelu.

- `needs_brief` je tabulka §2: kdy se výslech spustí (nový požadavek `fix_for_milestone`, otevřené rozšíření
  `later_extension`, `changes_intent` na dopady, karta `ready` s měřákem `evidence: thin` krátce). Řádek
  „člověk klikne ve Velínu“ přijde v řezu 3.
- `situation` složí spis požadavku (§3.1): vstupy doslova a podobné vstupy, ZÁMĚR, oblast, milník s kritérii,
  související karty se štítkem měřáku (`card_gauge`), pravidla a rozhodnutí. `collect_situation` fakta přečte.
- `clarity` je kontrola kritérií jasna (§4); stav `clear` nastaví jen `save_synthesis`, když nic nechybí.
- `save_synthesis` / `ask` jsou příkazy srdce `brief` a `ask` (§7): syntéza a nejvýš 3 otevřené otázky
  s doporučenou odpovědí, nejvýš 3 kola. Odpovídá jen člověk (řez 3).
- `requirement_wakes` / `card_hit` jsou spouštěč výslechu: jednou na stav (`heart_triggers`, klíč
  `trigger:brief:<rq>:<důvod>` a `trigger:brief:card:<uzel>:thin@<prostor>`).
"""
import json
import sqlite3

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas import card_gauge
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
           "thin": "karta k předání má málo podkladů, doplň kroky a soubory"}
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


def needs_brief(*, status, verdicts=(), brief_status=None, evidence=None):
    """Důvod výslechu podle tabulky §2, nebo None. Karta (`evidence` není None): `ready` + `thin` → `thin`.
    Požadavek: jen `open`; `changes_intent` mezi vstupy → `changes_intent` (i po jasnu, na dopady); s jasnem
    nic; zakládající vstup (první) `fix_for_milestone` → `new`, `later_extension` (už otevřený) → `opened`;
    `duplicate`, `done`, `extends_in_progress` a ostatní nic."""
    if evidence is not None:
        return "thin" if status == "ready" and evidence == "thin" else None
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
    """`brief` požadavku v `GET /api/intake`: `{status, questions, missing}`, bez spisu None."""
    if brief is None:
        return None
    return {"status": brief["status"], "questions": brief["questions"],
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


def requirement_wakes(db, since):
    """Kandidáti výslechu `[(prostor, požadavek, důvod)]`: otevřené požadavky se vstupem novějším než `since`
    (ISO čas), kterým `needs_brief` dá důvod a srdce na ten stav ještě nebudilo. Jen čte."""
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
                                 brief_status=brief["status"] if brief else None)
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


def card_hit(card):
    """Spouštěč krátkého výslechu karty (`triggers.wakes`, `extra`): `(klíč, vstup brief)`, nebo None."""
    if needs_brief(status=card.get("status"), evidence=card.get("evidence")) != "thin":
        return None
    return card_key(card["nodeId"], card.get("workspace")), {
        "type": "brief", "nodeId": card["nodeId"], "title": card.get("title") or card["nodeId"], "reason": "thin",
        "detail": card_gauge.THIN_REASON}
