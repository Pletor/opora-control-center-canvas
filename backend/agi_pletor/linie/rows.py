"""Řádky editoru Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §2): `<data>/projects/<id>/linie/rows.json`.

Tvar souboru `{"mapping": {"main": "main", "develop": "develop"}, "rows": [{id, name, type, ticketId, branch, base,
target, collapsed, order}]}`. Main a Develop jsou pevné řádky (nejdou změnit ani smazat), mapování je pevné.
Řádek je jen popisek v editoru: přidání **nezakládá** větev a přejmenování ji **nepřejmenuje** – žádný git tu neběží.
"""
import json
import threading
import uuid
from pathlib import Path

from backend.brain_opora.determinism.gate_payloads import GateError, invalid

TYPES = ("items", "work", "experiment", "fix")
MAPPING = {"main": "main", "develop": "develop"}
FIXED = [{"id": name, "name": name.capitalize(), "type": name, "ticketId": None, "branch": name, "base": None,
          "target": None, "collapsed": False, "order": order, "fixed": True} for order, name in enumerate(MAPPING)]
# Items je pevná hlavička bez vlastní větve: pod ní leží větve items/<díl> (do develop nebo feat větve, kde je díl potřeba).
FIXED.append({"id": "items", "name": "Items", "type": "items", "ticketId": None, "branch": None,
              "base": {"branch": "develop", "sha": None}, "target": None, "collapsed": False, "order": 2, "fixed": True})
LOCK = threading.Lock()  # čtení-změna-zápis souboru z více vláken serveru


def _path(data_root, project):
    return Path(data_root) / "projects" / project / "linie" / "rows.json"


def _stored(data_root, project):
    try:
        value = json.loads(_path(data_root, project).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    found = value.get("rows") if isinstance(value, dict) else None
    # staré řádky typu topic se čtou jako work (téma drželo práci, ne univerzální díl) (role topic zanikla)
    return [{**row, "type": "work" if row.get("type") == "topic" else row.get("type")}
            for row in found if isinstance(row, dict) and row.get("id")] if isinstance(found, list) else []


def _write(data_root, project, stored):
    path = _path(data_root, project)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"mapping": MAPPING, "rows": stored}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)  # celý soubor, nebo nic


def read(data_root, project):
    """`{mapping, rows}`: pevné Main a Develop první, pak pracovní řádky podle `order`."""
    return {"mapping": dict(MAPPING),
            "rows": [dict(row) for row in FIXED] + sorted(_stored(data_root, project), key=lambda r: r.get("order", 0))}


def _text(value, key, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise invalid(f"{key} je neprázdný text do {limit} znaků.", 'Například {"name": "Datový uzel", "type": "work"}.')
    return value.strip()


def _target(value):
    if value is not None and (not isinstance(value, str) or not value or any(c.isspace() for c in value)):
        raise invalid("target je název větve bez mezer nebo null.", 'Například "target": "develop".')
    return value


def _base(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"branch", "sha"} or not isinstance(value.get("branch"), str):
        raise invalid("base je {branch, sha?}.", 'Například "base": {"branch": "develop"}.')
    return {"branch": value["branch"], "sha": value.get("sha")}


def add(data_root, project, name, kind, base=None, target=None):
    if kind not in TYPES:
        raise invalid("type je " + ", ".join(TYPES) + ".", 'Například "type": "work".')
    row = {"id": "row_" + uuid.uuid4().hex[:12], "name": _text(name, "name"), "type": kind, "ticketId": None,
           "branch": None, "base": _base(base), "target": _target(target), "collapsed": False}
    with LOCK:
        stored = _stored(data_root, project)
        row["order"] = max((r.get("order", 0) for r in stored), default=1) + 1
        _write(data_root, project, [*stored, row])
    return row


def _find(stored, row_id):
    if any(row["id"] == row_id for row in FIXED):
        raise GateError(409, "row_fixed", "Main, Develop a Items jsou pevné řádky.", "Měňte jen pracovní řádky.")
    for row in stored:
        if row["id"] == row_id:
            return row
    raise GateError(404, "row_not_found", "Řádek Linie neexistuje.", "Řádky vrací GET /api/pletor/linie/board.")


def patch(data_root, project, row_id, changes):
    """Změní jen `name`, `branch`, `target`, `collapsed` (klíče, které přišly)."""
    with LOCK:
        stored = _stored(data_root, project)
        row = _find(stored, row_id)
        if "name" in changes:
            row["name"] = _text(changes["name"], "name")
        if "branch" in changes:  # řádek = větev: člověk přiřadí ručnímu řádku jeho větev (git tím nevzniká)
            row["branch"] = _target(changes["branch"])
        if "target" in changes:
            row["target"] = _target(changes["target"])
        if "collapsed" in changes:
            row["collapsed"] = bool(changes["collapsed"])
        _write(data_root, project, stored)
    return row


def remove(data_root, project, row_id, used):
    """Smaže prázdný řádek; řádek, na kterém leží kulička (`used` = rowId ticketů), je 409."""
    with LOCK:
        stored = _stored(data_root, project)
        _find(stored, row_id)
        if row_id in used:
            raise GateError(409, "row_in_use", "Na řádku leží kuličky; smazat jde jen prázdný řádek.",
                            "Nejdřív práci dokončete nebo zrušte.")
        _write(data_root, project, [row for row in stored if row["id"] != row_id])
    return {"removed": row_id}
