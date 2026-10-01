"""Registr rolí agenta: kdo si co pamatuje napříč projekty.

Role je trvalá kompetence (frontend, backend, databáze…), ne osoba a ne konkrétní projekt.
Data leží ve verzovaném `library/agent-roles.json` a čtou se jen odsud; nevalidní soubor se
hlásí jako chyba a nikdy se nenahrazuje odhadem ani demo daty (stejně jako knihovna pipeline).

Id role je zároveň `user` v OpenVikingu (`viking://user/{role}/…`), proto musí být tvaru
`role-<malá písmena, číslice, pomlčky>` — jinak by se paměť rozpadla po přejmenování.
"""

import hashlib
import json
import re

from backend.paths import REPO_ROOT

ROLES_FILE = REPO_ROOT / "library" / "agent-roles.json"
ROLE_KEYS = {"id", "label", "description"}
ROLE_ID = re.compile(r"role-[a-z0-9-]+")
MAX_ID = 60
MAX_TEXT = 400
MAX_ROLES = 100

_cache = {}


def _fail(message):
    raise ValueError("Registr rolí agenta je neplatný: " + message)


def _text(value, label, limit=MAX_TEXT):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        _fail(f"{label} musí být neprázdný text do {limit} znaků.")
    return value


def validate_roles(value):
    if not isinstance(value, dict) or set(value) != {"roles"} or not isinstance(value["roles"], list):
        _fail("očekávám objekt s polem roles.")
    items = value["roles"]
    if not items or len(items) > MAX_ROLES:
        _fail(f"roles musí mít 1 až {MAX_ROLES} položek.")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != ROLE_KEYS:
            _fail("role má neplatná pole; očekávám id, label a description.")
        _text(item["id"], "id role", MAX_ID)
        if not ROLE_ID.fullmatch(item["id"]):
            _fail(f"id role {item['id']} musí být tvaru role-<a-z0-9->.")
        if item["id"] in seen:
            _fail(f"duplicitní role {item['id']}.")
        seen.add(item["id"])
        _text(item["label"], "název role")
        _text(item["description"], "popis role")
    return items


def load(path=ROLES_FILE):
    """Seznam rolí; výsledek se drží v paměti, dokud se obsah souboru nezmění.

    Klíčem není čas úpravy: hodiny Windows tikají po zhruba 16 ms, takže dva rychlé
    zápisy dostanou stejné razítko a změna by se ztratila. Rozhoduje otisk obsahu.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Registr rolí agenta není dostupný: {path.name}.") from error
    stamp = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cached = _cache.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Registr rolí agenta je neplatný: soubor {path.name} není platný JSON ({error.msg})."
        ) from error
    items = validate_roles(raw)
    _cache[path] = (stamp, items)
    return items


def role_ids(path=ROLES_FILE):
    return tuple(item["id"] for item in load(path))


def role(role_id, path=ROLES_FILE):
    """Jedna role, nebo None; volající rozhodne, zda je neznámá role chyba."""
    return next((item for item in load(path) if item["id"] == role_id), None)
