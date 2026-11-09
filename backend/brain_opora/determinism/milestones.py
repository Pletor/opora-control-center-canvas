"""Milníky vstupní brány (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4, §5), bez modelu.

Srdce milník oblasti jen navrhne (`propose`, `opora_heart.py milestone`, stav `proposed`) a položí k němu eskalaci;
aktivovat nebo zamítnout ho smí jen člověk (`decide`, `POST /api/intake/milestone`). Aktivace nahradí dosavadní
aktivní milník oblasti (`superseded`, historie zůstává).

Karty kritéria `{id, text, cards[], verification?}` jsou uzavřené, když mají na plátně `done.confirmed`.
`closureDone` a `closureProgress` zachovávají uzavření; kompatibilní `progress` stále znamená uzavření.
Funkční `done` navíc vyžaduje společný integrační běh se všemi kladnými i zápornými testy přesně přijatého
zadání (`milestone_evidence.py`). Zdroj důkazů je Kancelář, nikoliv nezávislý ověřovatel. Výsledky se počítají,
neukládají. Spouštěč `milestone.done` (`wakes`) srdce probudí jednou na milník (klíč `trigger:milestone:<id>:done`
v `heart_triggers`) se seznamem odložených požadavků s podmínkou na ten milník; stav požadavků nemění.
"""
import uuid

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.brain_opora.determinism import milestone_evidence
from backend.canvas.graph import valid_id
from backend.canvas.opora_event_stage import confirmed_nodes
from database.repositories.heart_triggers import HeartTriggers
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements

TITLE, TEXT = 200, 300  # znaků názvu milníku a textu kritéria
CRITERIA, CARDS = 12, 30  # nejvýš kritérií na milník a karet na kritérium
ACTIONS = ("activate", "reject")
HINT = 'python opora_heart.py milestone --area A --title T --criterion "text::nodeId,nodeId"'


def trigger_key(milestone_id):
    return f"trigger:milestone:{milestone_id}:done"


def _text(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise invalid(f"{name} je neprázdný text do {limit} znaků.", HINT)
    return value.strip()


def criteria_of(items, known):
    """Kritéria `[{text, cards[]}]` → `[{id c1…, text, cards}]`; karta musí být uzel plátna (`known`)."""
    if not isinstance(items, list) or not 1 <= len(items) <= CRITERIA:
        raise invalid(f"criteria je 1 až {CRITERIA} kritérií.", HINT)
    result = []
    for number, item in enumerate(items, 1):
        if not isinstance(item, dict) or not {"text", "cards"} <= set(item) <= {"text", "cards", "verification"}:
            raise invalid("Kritérium je {text, cards[], verification?}.", HINT)
        cards = item["cards"]
        if not isinstance(cards, list) or not 1 <= len(cards) <= CARDS or not all(isinstance(c, str) for c in cards):
            raise invalid(f"Kritérium dokládá 1 až {CARDS} karet (ID uzlů).", HINT)
        unknown = [card for card in cards if card not in known]
        if unknown:
            raise GateError(404, "card_not_found", f"Karty {', '.join(unknown)} na plátně prostoru nejsou.",
                            "ID karet najdete ve snímku nebo v ctx tree.")
        result.append({"id": f"c{number}", "text": _text(item["text"], TEXT, "text kritéria"),
                       "cards": list(dict.fromkeys(cards)),
                       **({"verification": item["verification"]} if "verification" in item else {})})
    return result


def evaluate(db, project, milestone):
    """Milník s počítaným splněním: kritéria `{…, cards: [{id, done}], done}`, `done` a `progress` (0–100)."""
    cards = [card for criterion in milestone["criteria"] for card in criterion.get("cards", [])]
    closed = confirmed_nodes(db, project, milestone["workspaceId"], cards)
    criteria = [{**criterion, "cards": [{"id": card, "done": card in closed} for card in criterion.get("cards", [])],
                 "done": bool(criterion.get("cards")) and all(card in closed for card in criterion["cards"])}
                for criterion in milestone["criteria"]]
    unique = list(dict.fromkeys(cards))
    progress = round(100 * sum(card in closed for card in unique) / len(unique)) if unique else 0
    closure_done = bool(criteria) and all(item["done"] for item in criteria)
    verification = milestone_evidence.evaluate(db, project, milestone["workspaceId"], milestone["criteria"])
    return {**milestone, "criteria": criteria, "done": closure_done and verification["verified"],
            "closureDone": closure_done, "closureProgress": progress, "verification": verification, "progress": progress}


def reached(db, project, workspace=None):
    """Splněné aktivní milníky (prostoru, None = všech) s odloženými požadavky s podmínkou na ně."""
    found = []
    for milestone in IntakeMilestones(db).list(workspace, ("active",)):
        evaluated = evaluate(db, project, milestone)
        if evaluated["done"]:
            deferred = IntakeRequirements(db).deferred_until(milestone["workspaceId"], milestone["id"])
            found.append({"milestone": evaluated, "deferred": deferred})
    return found


def wakes(db, project, workspaces, at):
    """Spouštěč `milestone.done`: `[(prostor, vstup dávky)]` pro splněné aktivní milníky, kterým srdce ještě
    nebudilo (`workspaces` None = všechny prostory). Značku zapíše hned; transakci vlastní volající."""
    found, triggers = [], HeartTriggers(db)
    for item in reached(db, project):
        milestone = item["milestone"]
        space = milestone["workspaceId"]
        if workspaces is not None and space not in workspaces:
            continue
        if triggers.fire(trigger_key(milestone["id"]), space, at):
            found.append((space, {"type": "milestoneDone", "milestoneId": milestone["id"], "title": milestone["title"],
                                  "areaId": milestone["areaId"],
                                  "deferred": [{"id": rq["id"], "title": rq["title"]} for rq in item["deferred"]]}))
    return found


def _nodes(service, project, workspace):
    return {node.get("id"): node for node in service.view(project, workspace)["graph"]["nodes"]
            if isinstance(node, dict)}


def propose(service, session, area, title, criteria, now):
    """Návrh milníku srdcem (`POST /api/brain/heart/milestone`): oblast musí být uzel `area` prostoru srdce,
    karty kritérií uzly plátna. Uloží se jako `proposed`; aktivuje ho až člověk."""
    project, workspace = session["project_id"], session["workspace_id"]
    nodes = _nodes(service, project, workspace)
    if not isinstance(area, str) or nodes.get(area, {}).get("kind") != "area":
        raise GateError(404, "area_not_found", "Oblast v tomto pracovním prostoru neexistuje.",
                        "Oblast je uzel plátna druhu area (ctx tree).")
    milestone = {"id": "ms_" + uuid.uuid4().hex, "workspaceId": workspace, "areaId": area,
                 "title": _text(title, TITLE, "title"), "criteria": criteria_of(criteria, nodes),
                 "status": "proposed", "createdAt": now}
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            try:
                milestone_evidence.validate_criteria(db, project, workspace, milestone["criteria"])
            except (ValueError, TypeError, KeyError) as error:
                raise invalid(str(error), "Připněte kladné i záporné testy přijatého integračního zadání.") from error
            IntakeMilestones(db).insert(milestone)
    return {key: milestone[key] for key in ("id", "status", "areaId", "title", "criteria")}


def decide(service, payload):
    """Rozhodnutí člověka o návrhu (`POST /api/intake/milestone`): `activate` nahradí aktivní milník oblasti,
    `reject` zamítne návrh i aktivní milník (např. když plán srostl s duplicitou a karty zmizely; oblast pak
    nemá aktivní milník). `activate` jen u `proposed`, jinak 409."""
    keys = {"project", "workspace", "milestoneId", "action"}
    if not isinstance(payload, dict) or set(payload) != keys:
        raise invalid("Tělo je přesně {project, workspace, milestoneId, action}.",
                      '{"project": "<id>", "workspace": "main", "milestoneId": "ms_…", "action": "activate"}')
    project, workspace, action = payload["project"], payload["workspace"], payload["action"]
    if action not in ACTIONS:
        raise invalid("action je activate nebo reject.", "Aktivovat nebo zamítnout smí člověk, nebo agent při plné autonomii.")
    if not isinstance(project, str) or not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if not isinstance(workspace, str) or not valid_id(workspace):
        raise invalid("Neplatný pracovní prostor.", "Použijte main, draft nebo ID pracovního prostoru.")
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = IntakeMilestones(db)
            milestone = store.get(payload["milestoneId"]) if isinstance(payload["milestoneId"], str) else None
            if milestone is None or milestone["workspaceId"] != workspace:
                raise GateError(404, "milestone_not_found", "Milník v tomto pracovním prostoru neexistuje.",
                                "ID milníku (ms_…) je v GET /api/intake u oblasti v návrzích.")
            allowed = ("proposed", "active") if action == "reject" else ("proposed",)
            if milestone["status"] not in allowed:
                raise GateError(409, "milestone_not_proposed",
                                f"Milník je {milestone['status']}, " + ("zamítnout jde jen návrh nebo aktivní milník."
                                                                        if action == "reject" else "aktivovat jde jen návrh."),
                                "Nový milník navrhuje srdce (opora_heart.py milestone).")
            superseded = store.activate(milestone["id"])[1] if action == "activate" else None
            if action == "reject":
                store.reject(milestone["id"])
            status = store.get(milestone["id"])["status"]
    return {"id": milestone["id"], "status": status, "superseded": superseded}


def plan(db, project, workspace, areas):
    """Pohled „Požadavky a plán“ po oblastech: aktivní milník (kritéria hotovo/nehotovo, postup), návrhy milníků,
    otevřené a odložené požadavky (s podmínkou). Požadavky bez známé oblasti jdou do `unassigned`."""
    milestones = IntakeMilestones(db).list(workspace, ("active", "proposed"))
    requirements = IntakeRequirements(db).list(workspace, ("open", "deferred"))
    known, result = {area["id"] for area in areas}, []
    for area in areas:
        active = next((item for item in milestones if item["areaId"] == area["id"] and item["status"] == "active"), None)
        mine = [item for item in requirements if item["areaId"] == area["id"]]
        result.append({**area, "milestone": evaluate(db, project, active) if active else None,
                       "proposed": [item for item in milestones if item["areaId"] == area["id"]
                                    and item["status"] == "proposed"],
                       "requirements": [item for item in mine if item["status"] == "open"],
                       "deferred": [item for item in mine if item["status"] == "deferred"]})
    return result, [item for item in requirements if item["areaId"] not in known]
