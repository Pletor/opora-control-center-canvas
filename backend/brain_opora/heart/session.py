"""Relace srdce a její rotace (docs/brain-heart.md §2): `brain/session.json = {sessionId, batches, lastInputTokens}`.

Další dávka navazuje přes `--resume`. Když kontext posledního tahu předchozí dávky (`lastInputTokens`) přesáhl
`ROTATE_AT` tokenů, začne nová relace (`--session-id`) s čerstvým snímkem. Novou relaci začne i změněný prompt srdce
(`promptDigest`): navázaná relace by držela stará pravidla a příkazy z historie. Poškozený nebo chybějící soubor
= žádná relace (začne nová).

Velikost kontextu: `usage` výsledku `claude -p` je součet přes všechny tahy dávky (21 tahů po ~25k = 541k), takže
kontext neměří. Proto `context_tokens` bere `usage` posledního tahu hlavního vlákna ze `stream-json` (události
`assistant` bez `parent_tool_use_id`). Bez nich (jiný formát, prázdný výstup) odhadne kontext konce dávky z
kumulativního `usage`: každý tah čte z cache celý předchozí kontext a zapisuje jen přírůstek, takže konec ≈ zápisy
cache + čerstvý vstup + čtení prvního tahu, a to čtení je nejvýš průměrné čtení na tah (`read / num_turns`).
"""
import json
import uuid
from pathlib import Path

FILE = "session.json"
ROTATE_AT = 60_000
EMPTY = {"sessionId": None, "batches": 0, "lastInputTokens": 0}
INPUT_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
# Rozpad `usage` dávky do záznamu v `batches.jsonl` (aditivní pole vedle `inputTokens`).
PARTS = {"fresh": "input_tokens", "cacheRead": "cache_read_input_tokens",
         "cacheCreation": "cache_creation_input_tokens", "output": "output_tokens"}


def load(brain):
    """Stav relace z `brain/session.json`; cokoli nečitelného je `EMPTY`."""
    try:
        value = json.loads((Path(brain) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(EMPTY)
    if not isinstance(value, dict) or not isinstance(value.get("sessionId"), str):
        return dict(EMPTY)
    batches, tokens = value.get("batches"), value.get("lastInputTokens")
    state = {"sessionId": value["sessionId"], "batches": batches if isinstance(batches, int) else 0,
             "lastInputTokens": tokens if isinstance(tokens, int) else 0}
    if isinstance(value.get("promptDigest"), str):
        state["promptDigest"] = value["promptDigest"]
    return state


def choose(brain, new_id=uuid.uuid4, prompt_digest=None):
    """`(sessionId, resume)`: navázat na uloženou relaci, nebo po rotaci, změně promptu (či bez relace) začít novou."""
    state = load(brain)
    same_prompt = prompt_digest is None or state.get("promptDigest") == prompt_digest
    if state["sessionId"] and state["lastInputTokens"] <= ROTATE_AT and same_prompt:
        return state["sessionId"], True
    return str(new_id()), False


def _number(usage, key):
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) else 0


def input_tokens(usage):
    """Vstup včetně čtení a zápisu cache. U `usage` jednoho tahu je to velikost jeho kontextu, u `usage` výsledku
    součet přes všechny tahy dávky (pole `inputTokens` v deníku)."""
    return sum(_number(usage, key) for key in INPUT_KEYS)


def parts(usage):
    """`{fresh, cacheRead, cacheCreation, output}` z kumulativního `usage` výsledku dávky."""
    return {name: _number(usage, key) for name, key in PARTS.items()}


def last_turn_usage(stdout):
    """`usage` posledního tahu hlavního vlákna ze `stream-json` (poslední událost `assistant` s `usage` a bez
    `parent_tool_use_id`); bez takové události None."""
    last = None
    for line in (stdout or "").splitlines():
        if '"assistant"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") if isinstance(event, dict) and event.get("type") == "assistant" else None
        if isinstance(message, dict) and isinstance(message.get("usage"), dict) and not event.get("parent_tool_use_id"):
            last = message["usage"]
    return last


def context_tokens(stdout, result):
    """Velikost kontextu na konci dávky: přesně z posledního tahu (`last_turn_usage`), jinak odhad z kumulativního
    `usage` výsledku: zápisy cache + čerstvý vstup + čtení cache / počet tahů (viz docstring modulu)."""
    turn = last_turn_usage(stdout)
    if turn is not None:
        return input_tokens(turn)
    usage = (result or {}).get("usage")
    turns = (result or {}).get("num_turns")
    turns = turns if isinstance(turns, int) and turns > 0 else 1
    return (_number(usage, "input_tokens") + _number(usage, "cache_creation_input_tokens")
            + round(_number(usage, "cache_read_input_tokens") / turns))


def record(brain, session_id, tokens, prompt_digest=None):
    """Zapíše dokončenou dávku: stejná relace = `batches + 1`, nová relace začíná na 1."""
    state = load(brain)
    batches = state["batches"] + 1 if state["sessionId"] == session_id else 1
    value = {"sessionId": session_id, "batches": batches, "lastInputTokens": int(tokens)}
    if prompt_digest:
        value["promptDigest"] = prompt_digest
    path = Path(brain) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=1), encoding="utf-8")
    temporary.replace(path)
    return value
