"""Relace srdce a její rotace (docs/brain-heart.md §2): `brain/session.json = {sessionId, batches, lastInputTokens}`.

Další dávka navazuje přes `--resume`. Když vstup poslední dávky přesáhl `ROTATE_AT` tokenů, začne nová relace
(`--session-id`) s čerstvým snímkem. Poškozený nebo chybějící soubor = žádná relace (začne nová).
"""
import json
import uuid
from pathlib import Path

FILE = "session.json"
ROTATE_AT = 60_000
EMPTY = {"sessionId": None, "batches": 0, "lastInputTokens": 0}


def load(brain):
    """Stav relace z `brain/session.json`; cokoli nečitelného je `EMPTY`."""
    try:
        value = json.loads((Path(brain) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(EMPTY)
    if not isinstance(value, dict) or not isinstance(value.get("sessionId"), str):
        return dict(EMPTY)
    batches, tokens = value.get("batches"), value.get("lastInputTokens")
    return {"sessionId": value["sessionId"], "batches": batches if isinstance(batches, int) else 0,
            "lastInputTokens": tokens if isinstance(tokens, int) else 0}


def choose(brain, new_id=uuid.uuid4):
    """`(sessionId, resume)`: navázat na uloženou relaci, nebo po rotaci (či bez relace) začít novou."""
    state = load(brain)
    if state["sessionId"] and state["lastInputTokens"] <= ROTATE_AT:
        return state["sessionId"], True
    return str(new_id()), False


def input_tokens(usage):
    """Velikost kontextu dávky: vstup včetně čtení a zápisu cache (`usage` výsledku `claude -p`)."""
    if not isinstance(usage, dict):
        return 0
    keys = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    return sum(value for value in (usage.get(key) for key in keys) if isinstance(value, int))


def record(brain, session_id, tokens):
    """Zapíše dokončenou dávku: stejná relace = `batches + 1`, nová relace začíná na 1."""
    state = load(brain)
    batches = state["batches"] + 1 if state["sessionId"] == session_id else 1
    value = {"sessionId": session_id, "batches": batches, "lastInputTokens": int(tokens)}
    path = Path(brain) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=1), encoding="utf-8")
    temporary.replace(path)
    return value
