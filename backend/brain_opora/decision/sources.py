"""Levné podvolání RLM: seřadí oddíly plátna k dotazu jedním voláním Jev (README.md, sekce RLM).

Asistent nečte celé plátno. Pošle sem kandidáty (id karty a začátek jejího textu) a dostane
pořadí s pravděpodobností. Jev nic nepíše a nerozhoduje; pořadí je jen údaj, kam nahlédnout
nejdřív. Bez klíče nebo při poruše vrací `unavailable` a asistent hledá dál bez něj.
"""

import math
import re

MAX_QUERY = 2000
MAX_CANDIDATES = 255
MAX_TEXT = 300
MAX_TOP = 50
CANDIDATE_KEYS = {"id", "text"}
CANDIDATE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
UNAVAILABLE = {"status": "unavailable"}


def _query(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_QUERY:
        raise ValueError(f"Dotaz pro řazení musí být neprázdný text do {MAX_QUERY} znaků.")
    return value.strip()


def _candidates(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_CANDIDATES:
        raise ValueError(f"Kandidátů musí být 1 až {MAX_CANDIDATES}.")
    criteria = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != CANDIDATE_KEYS:
            raise ValueError("Kandidát vyžaduje přesně pole id a text.")
        cid, text = item["id"], item["text"]
        if not isinstance(cid, str) or not CANDIDATE_ID.fullmatch(cid):
            raise ValueError("ID kandidáta musí odpovídat [A-Za-z0-9_-]{1,128}.")
        if cid in criteria:
            raise ValueError(f"Kandidát {cid} je v seznamu dvakrát.")
        if not isinstance(text, str):
            raise ValueError("Text kandidáta musí být řetězec.")  # noqa: TRY004 — 409 přes handler aplikace
        criteria[cid] = text[:MAX_TEXT]
    return criteria


def _top(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TOP:
        raise ValueError(f"top musí být celé číslo 1 až {MAX_TOP}.")
    return value


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def question(query, criteria):
    """Jedna otázka `choice`: možnosti jsou id karet, jejich popis je začátek textu karty."""
    return {"rank": {"type": "choice", "instructions": f"Který oddíl nejlépe odpovídá dotazu: {query}?",
                     "criteria": criteria}}


def _ranked(answer, criteria):
    """Pravděpodobnosti známých id seřazené sestupně; neznámé id (halucinace) vypadne."""
    if not isinstance(answer, dict):
        return []
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict):
        # Bez rozložení zůstane aspoň vybraná možnost s jistotou.
        probabilities = {answer.get("choice"): answer.get("confidence")} if isinstance(answer.get("choice"), str) else {}
    order = {cid: position for position, cid in enumerate(criteria)}
    rows = [(cid, p) for cid, p in ((cid, _probability(p)) for cid, p in probabilities.items())
            if cid in order and p is not None]
    rows.sort(key=lambda row: (-row[1], order[row[0]]))
    return [{"id": cid, "p": p} for cid, p in rows]


def rank(query, candidates, top, *, evaluate):
    """`{status: "ok", ranked: [{id, p}]}` (nejvýš `top`), nebo `{status: "unavailable"}`.

    Neplatný vstup je `ValueError` (409); porucha Jev nikdy nevyhodí.
    """
    query, criteria, top = _query(query), _candidates(candidates), _top(top)
    try:
        answers = evaluate({"query": query}, question(query, criteria))
    except Exception:  # noqa: BLE001 — Jev je zrychlení, ne podmínka; injektovaný klient nesmí shodit dotaz
        return dict(UNAVAILABLE)
    ranked = _ranked(answers.get("rank") if isinstance(answers, dict) else None, criteria)
    if not ranked:
        return dict(UNAVAILABLE)
    return {"status": "ok", "ranked": ranked[:top]}
