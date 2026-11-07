"""Idempotence operací Linie (docs/navrhy/2026-11-06-linie-rebrand.md §7 bod 5): klíč + digest obsahu.

`<data>/projects/<p>/linie/idempotency.json` = `{"<scope>:<key>": {digest, at}}`. Stejný klíč se stejným obsahem je
opakování (`existing`), s jiným obsahem 409 `idempotency_conflict`. `once` drží zámek projektu přes ověření, operaci
i zápis klíče a operaci dá deterministické ID z klíče (`ident`): po pádu mezi operací a zápisem klíče opakování
najde už založený záznam podle ID a nic nezdvojí. Klíč se zapisuje až po úspěchu, takže opravený neplatný požadavek
se stejným klíčem projde.
"""
import hashlib
import json
from pathlib import Path

from backend.agi_pletor.linie import jsonfile
from backend.brain_opora.determinism.gate_payloads import GateError


def _path(data_root, project):
    return Path(data_root) / "projects" / project / "linie" / "idempotency.json"


def digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def ident(scope, key):
    """Deterministické ID operace z klíče (32 hex znaků)."""
    return hashlib.sha256(f"{scope}:{key}".encode("utf-8")).hexdigest()[:32]


def claim(data_root, project, scope, key, payload, at=None, *, write=True):
    """`existing` (stejný klíč i obsah) nebo `new` (s `write` klíč zapíše); jiný obsah 409 `idempotency_conflict`."""
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise GateError(422, "invalid_payload", "idempotencyKey je neprázdný řetězec do 200 znaků.",
                        "Pošlete stejný klíč při opakování téhož požadavku.")
    name, mine, found = f"{scope}:{key}", digest(payload), {}

    def change(entries):
        entries = entries if isinstance(entries, dict) else {}
        found["entry"] = entries.get(name)
        if found["entry"] is None and write:
            return {**entries, name: {"digest": mine, "at": at}}
        return entries
    if write:
        jsonfile.update(_path(data_root, project), {}, change)
    else:
        change(jsonfile.read(_path(data_root, project), {}))
    entry = found["entry"]
    if entry and entry.get("digest") != mine:
        raise GateError(409, "idempotency_conflict", f"Klíč {key} už nese jiný obsah.",
                        "Nový požadavek pošlete s novým klíčem; opakování se stejným obsahem.")
    return "existing" if entry else "new"


def once(service, project, scope, key, payload, act, at=None):
    """`act(id)`: bez klíče `id = None`, jinak `ident(scope, key)` pod zámkem projektu; klíč se zapíše po úspěchu."""
    if key is None:
        return act(None)
    with service.lock_for(project):
        claim(service.root, project, scope, key, payload, at, write=False)
        result = act(ident(scope, key))
        claim(service.root, project, scope, key, payload, at)
        return result
