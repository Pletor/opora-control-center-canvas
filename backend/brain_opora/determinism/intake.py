"""Vstupní brána požadavků, vrstva determinismu (docs/navrhy/2026-10-30-vstupni-brana.md §4, řez 1).

Každá věta člověka nebo pracovníka (zpráva v panelu srdce, lístek `change` / `ask`, nový fragment Schránky
`brief` / `question`) se zapíše jako neměnný vstup `ie_…` s otiskem: sha256 normalizovaného textu
(malá písmena, bez diakritiky a interpunkce, zúžené mezery). Stejný otisk ve stejném pracovním prostoru =
stanovisko `duplicate` (převezme požadavek, oblast a milník dřívějšího vstupu), jinak `pending`
a rozhodne srdce. Ke vstupu se navíc spočítají kandidáti: nejbližší 3 dřívější vstupy podle bm25 z FTS5.
Kandidáti se neukládají, jdou jen do řádku vstupu pro srdce. Nic tu nevolá model; `pending` může před dávkou
zařadit Jev (`backend/brain_opora/decision/intake.py`, řez 2). Srdce stanovisko potvrdí nebo opraví (`confirm`,
`opora_heart.py intake`, vrstva `heart`).

Zápis vstupu nikdy nesmí shodit původní tok (zprávu, lístek, fragment): `safe_record` chybu jen zaloguje
a vrátí None; částečný zápis vrátí savepoint.
"""
import hashlib
import logging
import re
import sqlite3
import time
import unicodedata
import uuid

from backend.brain_opora.determinism import brief, milestones, requirements
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id
from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries

LOGGER = logging.getLogger(__name__)
SOURCES = ("heart_message", "gate_change", "gate_ask", "brief_fragment")
CANDIDATES = 3
QUERY_TERMS = 32  # nejvýš slov ve výrazu FTS5
RECENT = 8  # vstupů v sekci VSTUPY snímku
LIST = 50  # vstupů v GET /api/intake
UNDECIDED = ("determinism", "jev")  # vrstvy vstupů, které snímek ukazuje (srdce je ještě nepotvrdilo)
VERDICTS = ("done", "extends_in_progress", "fix_for_milestone", "changes_intent", "later_extension", "needs_info")
REASON = 300  # znaků zdůvodnění srdce
NON_WORD = re.compile(r"[\W_]+", re.UNICODE)


def normalize(text):
    """Malá písmena, bez diakritiky a interpunkce, mezery zúžené na jednu."""
    plain = "".join(char for char in unicodedata.normalize("NFKD", str(text or "").lower())
                    if not unicodedata.combining(char))
    return " ".join(NON_WORD.sub(" ", plain).split())


def fingerprint(text):
    """sha256 normalizovaného textu (hex)."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def query(text):
    """Výraz FTS5 ze slov normalizovaného textu: slova v uvozovkách spojená OR, bez opakování; prázdný = ""."""
    words = list(dict.fromkeys(word for word in normalize(text).split() if len(word) > 1))[:QUERY_TERMS]
    return " OR ".join(f'"{word}"' for word in words)


def candidates(db, entry, limit=CANDIDATES):
    """ID nejbližších dřívějších vstupů prostoru podle bm25 (bez vstupu samotného)."""
    expression = query(entry["text"])
    if not expression:
        return []
    return IntakeEntries(db).similar(entry["workspaceId"], expression, entry["id"], entry["createdAt"], limit)


def record(db, workspace, source, source_ref, text, created_at):
    """Zapíše vstup a vrátí ho i s `candidates` (ID, neukládají se). Prázdný text po normalizaci = None."""
    if source not in SOURCES:
        raise ValueError(f"Neznámý zdroj vstupu: {source}")
    text = str(text or "").strip()
    if not normalize(text):
        return None
    store, mark = IntakeEntries(db), fingerprint(text)
    earlier = store.first_with(workspace, mark)
    entry = {"id": "ie_" + uuid.uuid4().hex, "workspaceId": workspace, "source": source, "sourceRef": source_ref,
             "text": text, "fingerprint": mark, "createdAt": created_at, "layer": "determinism",
             "confidence": None, "costUsd": 0.0, "jevCalls": 0}
    if earlier is not None:
        entry |= {"verdict": "duplicate", "areaId": earlier["areaId"], "milestoneId": earlier["milestoneId"],
                  "requirementId": earlier["requirementId"], "reason": f"shodná věta jako {earlier['id']}"}
    else:
        entry |= {"verdict": "pending", "areaId": None, "milestoneId": None, "requirementId": None,
                  "reason": "bez shody otisku, stanovisko dá srdce"}
    store.insert(entry)
    return {**entry, "candidates": candidates(db, entry)}


def safe_record(db, workspace, source, source_ref, text, created_at):
    """`record` pod savepointem: chyba se zaloguje, zápis vstupu se vrátí a volající pokračuje (None)."""
    try:
        db.execute("SAVEPOINT intake_record")
    except sqlite3.Error:
        LOGGER.exception("Vstupní brána: savepoint pro vstup %s nešel založit.", source)
        return None
    try:
        entry = record(db, workspace, source, source_ref, text, created_at)
    except Exception:  # noqa: BLE001 - vstup nesmí shodit zprávu, lístek ani fragment
        LOGGER.exception("Vstupní brána: vstup %s (%s) nešel zapsat.", source, source_ref)
        try:
            db.execute("ROLLBACK TO intake_record")
            db.execute("RELEASE intake_record")
        except sqlite3.Error:
            LOGGER.exception("Vstupní brána: savepoint vstupu %s nešel vrátit.", source)
        return None
    db.execute("RELEASE intake_record")
    return entry


def line_info(entry):
    """Zkratka vstupu pro řádek dávky srdce: `{id, verdict, layer, areaId, confidence, candidates}`."""
    return {"id": entry["id"], "verdict": entry["verdict"], "layer": entry.get("layer"), "areaId": entry.get("areaId"),
            "confidence": entry.get("confidence"), "candidates": list(entry.get("candidates") or [])}


def for_source(db, source, source_ref):
    """Zkratka vstupu ze zdroje (lístek) s kandidáty spočtenými znovu, nebo None."""
    entry = IntakeEntries(db).by_source(source, source_ref)
    return None if entry is None else line_info({**entry, "candidates": candidates(db, entry)})


def recent(db, workspace, limit=RECENT):
    """Poslední vstupy prostoru, které srdce ještě nepotvrdilo (vrstva determinismu nebo Jevu), pro sekci VSTUPY."""
    return IntakeEntries(db).recent(workspace, limit, layers=UNDECIDED)


def confirm(service, session, entry_id, verdict, reason="", requirement=None, title=None, open_condition=None):
    """Srdce potvrdí nebo opraví stanovisko vstupu svého prostoru (vrstva `heart`); `POST /api/brain/heart/intake`.
    Oblast a počet volání Jevu zůstanou, jistota Jevu se smaže. Neznámé stanovisko 422, cizí vstup 404.
    `requirement` (`new` s `title` [a `open_condition`], nebo `rq_…`) vstup naváže na požadavek (`requirements.attach`)."""
    requirements.check(requirement, title, open_condition)
    if verdict not in VERDICTS:
        raise invalid(f"Neznámé stanovisko {verdict!r}.", "Stanovisko je jedno z: " + ", ".join(VERDICTS) + ".")
    if not isinstance(reason, str) or len(reason) > REASON or "\0" in reason:
        raise invalid(f"reason je text do {REASON} znaků.", "Jedna věta, proč toto stanovisko.")
    project, workspace = session["project_id"], session["workspace_id"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = IntakeEntries(db)
            entry = store.get(entry_id) if isinstance(entry_id, str) else None
            if entry is None or entry["workspaceId"] != workspace:
                raise GateError(404, "intake_entry_not_found", "Vstup v tomto pracovním prostoru neexistuje.",
                                "ID vstupu (ie_…) je ve snímku v sekci VSTUPY nebo v řádku vstupu dávky.")
            store.set_verdict(entry_id, verdict=verdict, layer="heart", reason=reason.strip() or f"srdce: {verdict}")
            requirements.attach(db, entry, verdict, requirement, title, open_condition,
                                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            entry = store.get(entry_id)
    return {key: entry[key] for key in ("id", "verdict", "layer", "areaId", "reason", "requirementId")}


def areas(service, project, workspace):
    """Oblasti plátna (`kind == "area"`) pracovního prostoru; nečitelný graf = žádné."""
    try:
        nodes = service.view(project, workspace)["graph"]["nodes"]
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
        return []
    return [{"id": node["id"], "name": node.get("name") or node["id"]}
            for node in nodes if isinstance(node, dict) and node.get("kind") == "area"]


def _check_scope(service, project, workspace):
    if not isinstance(project, str) or not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje nebo chybí ?project=.",
                        "ID projektu najdete v GET /api/bootstrap.")
    if not isinstance(workspace, str) or not valid_id(workspace):
        raise invalid("Chybí nebo je neplatné ?workspace=.", "Přidejte ?project=<id>&workspace=<main | draft | id>.")
    if workspace not in ("draft", "main") and not any(row["id"] == workspace for row in service.workspaces(project)):
        raise GateError(404, "workspace_not_found", "Pracovní prostor v projektu neexistuje.",
                        "Použijte main, draft nebo ID pracovního prostoru projektu.")


def _with_briefs(db, workspace, areas, unassigned):
    """Požadavky dostanou `brief: {status, questions, missing}` výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §7),
    bez spisu `None`."""
    found = IntakeBriefs(db).of_workspace(workspace)

    def mark(items):
        return [{**item, "brief": brief.view(found.get(item["id"]))} for item in items]

    return ([{**area, "requirements": mark(area["requirements"]), "deferred": mark(area["deferred"])}
             for area in areas], mark(unassigned))


def overview(service, project, workspace, limit=LIST):
    """`GET /api/intake`, pohled „Požadavky a plán“: oblasti s aktivním milníkem (kritéria hotovo/nehotovo, postup),
    návrhy milníků, otevřené a odložené požadavky (`milestones.plan`, každý s `brief` výslechu), požadavky bez oblasti
    (`unassigned`),
    posledních `limit` vstupů a počty `pending` / `duplicates`. Jen čtení; neznámý projekt nebo prostor 404,
    chybějící prostor 422."""
    _check_scope(service, project, workspace)
    found = areas(service, project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        store = IntakeEntries(db)
        entries, counts = store.recent(workspace, limit), store.counts(workspace)
        found, unassigned = milestones.plan(db, project, workspace, found)
        found, unassigned = _with_briefs(db, workspace, found, unassigned)
    return {"areas": found, "unassigned": unassigned, "entries": entries, "pending": counts.get("pending", 0),
            "duplicates": counts.get("duplicate", 0)}
