"""Tvar revize fragmentu schránky a čtení posledních revizí (docs/navrh-schranka-zadani.md).

Revize je řádek `brief_fragment_revisions`; data revize jsou sloupce `COLUMNS`. Stejný tvar
používá zápis služby (`brief_vault.py`) i uložená verze plátna (`version_content.STORES`).
"""

from typing import NoReturn

from backend.canvas.graph import valid_id
from backend.editor.brief_vault.brief_vault_disciplines import DISCIPLINE_IDS, discipline_from_track

COLUMNS = ("parent_id", "scope_node_id", "ord", "kind", "title", "text", "stage", "mvp", "note", "by", "actor", "deleted",
           "discipline")
# `research` = ověření proveditelnosti, `question` = otázka K upřesnění; obojí je poznámka k fragmentu, ne kus zadání.
KINDS = ("brief", "research", "question")
STAGES = ("draft", "research", "ready")
# `proposed` navrhuje agent; `yes` / `no` rozhoduje jen člověk.
MVP_VALUES = ("none", "proposed", "yes", "no")
ACTORS = ("human", "agent", "unknown", "")
MAX_TITLE, MAX_TEXT, MAX_NOTE, MAX_BY = 160, 64000, 1000, 120
# Strop hloubky fraktálu (kořen = 1): hlubší strom nejde založit (409) a čtení ho nevnoří dál.
MAX_DEPTH = 32
# Revize, kterou obnova verze plátna zapíše fragmentu vzniklému až po verzi: měkce smazaný
# a prázdný. Starší revize s doslovným textem v tabulce zůstávají.
TOMBSTONE = {"parent_id": None, "scope_node_id": None, "ord": 0, "kind": "brief", "title": "", "text": "",
             "stage": "draft", "mvp": "none", "note": "", "by": "", "actor": "", "deleted": 1, "discipline": None}


class BadRequest(ValueError):
    """Chybný tvar požadavku (např. kořen bez disciplíny): router ho vrací jako 400, ne 409 (konflikt stavu)."""


def fail(message) -> NoReturn:
    raise ValueError("Schránka zadání: " + message)


def bad_request(message) -> NoReturn:
    raise BadRequest("Schránka zadání: " + message)


def text_of(value, limit, label, allow_empty=True):
    if not isinstance(value, str) or "\0" in value or len(value) > limit or (not allow_empty and not value.strip()):
        fail(f"{label} musí být {'neprázdný ' if not allow_empty else ''}text do {limit} znaků bez NUL.")
    return value


def validate_record(data):
    """Data jedné revize (bez klíče a času); vrací je beze změny."""
    if not isinstance(data, dict) or set(data) != set(COLUMNS):
        fail("revize fragmentu má neplatná pole.")
    if data["parent_id"] is not None and not valid_id(data["parent_id"]):
        fail("parent_id má neplatný identifikátor.")
    scope = data["scope_node_id"]
    if scope is not None and scope != "" and not valid_id(scope):
        fail("scope_node_id má neplatný identifikátor.")
    if data["parent_id"] is not None and scope is not None:
        fail("schránku připíná ke kartě jen kořen; dítě má jen rodiče.")
    if type(data["ord"]) is not int or data["ord"] < 0:
        fail("ord musí být nezáporné celé číslo.")
    for key, allowed in (("kind", KINDS), ("stage", STAGES), ("mvp", MVP_VALUES), ("actor", ACTORS)):
        if data[key] not in allowed:
            fail(f"{key} musí být jedna z hodnot {', '.join(repr(item) for item in allowed)}.")
    text_of(data["title"], MAX_TITLE, "title")
    text_of(data["text"], MAX_TEXT, "text")
    text_of(data["note"], MAX_NOTE, "note")
    text_of(data["by"], MAX_BY, "by")
    if data["deleted"] not in (0, 1) or type(data["deleted"]) is not int:
        fail("deleted musí být 0 nebo 1.")
    if data["discipline"] is not None and data["discipline"] not in DISCIPLINE_IDS:
        fail("discipline musí být id disciplíny nebo null.")
    return data


def discipline_of(value, *, allow_null):
    """Disciplína z požadavku: id z tabulky §2, u dítěte i null (dědí)."""
    if value is None and allow_null:
        return None
    if not isinstance(value, str) or value not in DISCIPLINE_IDS:
        bad_request("discipline musí být jedna z " + ", ".join(DISCIPLINE_IDS)
                    + (" nebo null (dědí od rodiče)." if allow_null else "; kořen schránky disciplínu nese vždy."))
    return value


def discipline_payload(payload, key="discipline"):
    """Hodnota disciplíny z požadavku; `track` je alias do K5, pak smazat (ux → ux, logic → be, null → null).

    Vrací (je-li uvedena, hodnota). Obě pole naráz = 400; neznámá stopa = 400."""
    if "track" in payload:
        if key in payload:
            bad_request("pošlete jen discipline (track je dočasný alias).")
        track = payload["track"]
        if track is not None and discipline_from_track(track) is None:
            bad_request("track (alias do K5) musí být \"ux\", \"logic\" nebo null; použijte discipline.")
        return True, discipline_from_track(track)
    return key in payload, payload.get(key)


def effective_disciplines(rows):
    """Platná disciplína každého fragmentu {id: id|None}: `discipline` nejbližšího předka včetně sebe.

    Bez rekurze: každý fragment jde nahoru jen k první známé odpovědi (memo), cyklus nebo chybějící
    rodič končí jako „nezařazené“. Celkem O(n) kroků i pro strom hlubší než `MAX_DEPTH`.
    """
    result = {}
    for start in rows:
        chain, cursor, seen, found = [], start, set(), None
        while cursor in rows and cursor not in seen:
            if cursor in result:
                found = result[cursor]
                break
            seen.add(cursor)
            chain.append(cursor)
            if rows[cursor].get("discipline") is not None:
                found = rows[cursor]["discipline"]
                break
            cursor = rows[cursor]["parent_id"]
        for fragment_id in chain:
            result[fragment_id] = found
    return result


def data_of(row):
    return {column: row[column] for column in COLUMNS}


def public(row, *, with_text=False):
    """Revize pro API: camelCase, bez textu jen s délkou."""
    item = {"id": row["fragment_id"], "revision": row["revision"], "parentId": row["parent_id"],
            "scopeNodeId": row["scope_node_id"], "ord": row["ord"], "kind": row["kind"], "title": row["title"],
            "stage": row["stage"], "mvp": row["mvp"], "note": row["note"], "by": row["by"], "actor": row["actor"],
            "at": row["saved_at"], "deleted": bool(row["deleted"]), "chars": len(row["text"]),
            "discipline": row["discipline"]}
    if with_text:
        item["text"] = row["text"]
    return item


def latest_rows(db, project, workspace, fragment_ids=None):
    """Poslední revize každého fragmentu prostoru (volitelně jen vybraných), {id: řádek}."""
    query = ("SELECT * FROM brief_fragment_revisions AS t WHERE project_id=? AND workspace_id=? AND revision="
             "(SELECT MAX(revision) FROM brief_fragment_revisions WHERE project_id=t.project_id"
             " AND workspace_id=t.workspace_id AND fragment_id=t.fragment_id)")
    params = [project, workspace]
    if fragment_ids is not None:
        ids = sorted(set(fragment_ids))
        if not ids:
            return {}
        query += f" AND fragment_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    return {row["fragment_id"]: dict(row) for row in db.execute(query, params)}


def history_rows(db, project, workspace, fragment_id):
    return [dict(row) for row in db.execute(
        "SELECT * FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? AND fragment_id=? ORDER BY revision",
        (project, workspace, fragment_id))]


def text_revisions(db, project, workspace, fragment_ids=None):
    """Revize, ve které se naposledy změnil TEXT fragmentu, {id: revize}.

    „Změněno po vložení“ porovnává odkaz karty jen s ní: revize, které mění jen metadata
    (propose-mvp, stage, výsledek výzkumu), kartě zadání nemění.
    """
    query = ("SELECT fragment_id, MAX(revision) AS revision FROM (SELECT fragment_id, revision, text,"
             " LAG(text) OVER (PARTITION BY fragment_id ORDER BY revision) AS previous"
             " FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=?{only})"
             " WHERE previous IS NULL OR previous != text GROUP BY fragment_id")
    params = [project, workspace]
    only = ""
    if fragment_ids is not None:
        ids = sorted(set(fragment_ids))
        if not ids:
            return {}
        only = f" AND fragment_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    return {row["fragment_id"]: row["revision"] for row in db.execute(query.format(only=only), params)}

