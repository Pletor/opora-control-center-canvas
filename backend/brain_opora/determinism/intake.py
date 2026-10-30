"""Vstupní brána požadavků, vrstva determinismu (docs/navrhy/2026-10-30-vstupni-brana.md §4, řez 1).

Každá věta člověka nebo pracovníka (zpráva v panelu srdce, lístek `change` / `ask`, nový fragment Schránky
`brief` / `question`) se zapíše jako neměnný vstup `ie_…` s otiskem: sha256 normalizovaného textu
(malá písmena, bez diakritiky a interpunkce, zúžené mezery). Stejný otisk ve stejném pracovním prostoru =
stanovisko `duplicate` (převezme požadavek, oblast a milník dřívějšího vstupu), jinak `pending`
a rozhodne srdce. Ke vstupu se navíc spočítají kandidáti: nejbližší 3 dřívější vstupy podle bm25 z FTS5.
Kandidáti se neukládají, jdou jen do řádku vstupu pro srdce. Nic tu nevolá model.

Zápis vstupu nikdy nesmí shodit původní tok (zprávu, lístek, fragment): `safe_record` chybu jen zaloguje
a vrátí None; částečný zápis vrátí savepoint.
"""
import hashlib
import logging
import re
import sqlite3
import unicodedata
import uuid

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id
from database.repositories.intake_entries import IntakeEntries

LOGGER = logging.getLogger(__name__)
SOURCES = ("heart_message", "gate_change", "gate_ask", "brief_fragment")
CANDIDATES = 3
QUERY_TERMS = 32  # nejvýš slov ve výrazu FTS5
RECENT = 8  # vstupů v sekci VSTUPY snímku
LIST = 50  # vstupů v GET /api/intake
OPEN = ("pending", "duplicate")  # stanoviska, která snímek ukazuje (řez 1 jiná nemá)
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
    """Zkratka vstupu pro řádek dávky srdce: `{id, verdict, candidates}`."""
    return {"id": entry["id"], "verdict": entry["verdict"], "candidates": list(entry.get("candidates") or [])}


def for_source(db, source, source_ref):
    """Zkratka vstupu ze zdroje (lístek) s kandidáty spočtenými znovu, nebo None."""
    entry = IntakeEntries(db).by_source(source, source_ref)
    return None if entry is None else line_info({**entry, "candidates": candidates(db, entry)})


def recent(db, workspace, limit=RECENT):
    """Poslední vstupy prostoru se stanoviskem `pending` / `duplicate` pro sekci VSTUPY snímku."""
    return IntakeEntries(db).recent(workspace, limit, OPEN)


def _areas(service, project, workspace):
    """Oblasti plátna (`kind == "area"`) pracovního prostoru; nečitelný graf = žádné."""
    try:
        nodes = service.view(project, workspace)["graph"]["nodes"]
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
        return []
    return [{"id": node["id"], "name": node.get("name") or node["id"], "milestone": None, "requirements": []}
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


def overview(service, project, workspace, limit=LIST):
    """`GET /api/intake`: oblasti, posledních `limit` vstupů a počty `pending` / `duplicates`. Jen čtení;
    neznámý projekt nebo prostor 404, chybějící prostor 422."""
    _check_scope(service, project, workspace)
    areas = _areas(service, project, workspace)
    with service.reading(project):
        store = IntakeEntries(service.db_for(project))
        entries, counts = store.recent(workspace, limit), store.counts(workspace)
    return {"areas": areas, "entries": entries, "pending": counts.get("pending", 0),
            "duplicates": counts.get("duplicate", 0)}
