"""Zbytek zrušených kol karty (rozhodnutí vlastníka 23. 10.; historie pokusů je `resultHistory` v node-brief).

Kola se už neotevírají ani nezamrazují (tabulka `card_rounds` zůstává, prázdná). Stav uzlu ale
smí dál nést starší klíč `round = {number, openedAt, by, reason}`, protože ho jako podmínku čte
OporaHub obsah (`opora_content_sources`, `opora_content_changes`). Klíč nikdo nemění: obecný
zápis stavu ho jen převezme beze změny.
"""

from backend.canvas.activity_log import require_authority

ROUND_KEYS = {"number", "openedAt", "by", "reason"}
MAX_REASON = 2000
MAX_ROUNDS = 200


def _fail(message):
    raise ValueError("Neplatné kolo karty: " + message)


def validate_round(value, node_id=""):
    """Tvar staršího `nodes[].round`; kolo 1 se neukládá (chybějící klíč)."""
    if not isinstance(value, dict) or set(value) != ROUND_KEYS:
        _fail(f"round[{node_id}] má pole number, openedAt, by, reason.")
    if type(value["number"]) is not int or not 2 <= value["number"] <= MAX_ROUNDS:
        _fail(f"číslo kola musí být celé číslo 2 až {MAX_ROUNDS}.")
    for key, limit in (("openedAt", 40), ("by", 120), ("reason", MAX_REASON)):
        if not isinstance(value[key], str) or "\0" in value[key] or len(value[key]) > limit:
            _fail(f"{key} kola musí být text do {limit} znaků.")
    return value


def guard_state_write(actor, previous_state, state):
    """Kolo karty je zrušené: `round` se zápisem stavu nemění (výjimkou je jen server, `actor == "system"`)."""
    if actor == "system":
        return
    before = previous_state.get("nodes", {})
    for node_id, node in state.get("nodes", {}).items():
        if node.get("round") == before.get(node_id, {}).get("round"):
            continue
        message = "Kola karty jsou zrušená; číslo kola karty se nemění."
        require_authority(actor, message)
        raise ValueError(message)
