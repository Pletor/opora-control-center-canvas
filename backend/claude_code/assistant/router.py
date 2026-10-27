"""Směrovač podkladů asistenta přes TypeSafe Jev (docs/asistent.md §13.2).

Před zprávou člověka se jedním voláním zeptá, který podklad Opory odpověď potřebuje. Výsledek
je jen údaj (`hint`) v kontextu zprávy; model ho smí ignorovat. Bez klíče nebo při poruše
vrátí `None` a zpráva odejde beze změny.
"""

from __future__ import annotations

MAX_STATE_TEXT = 4000
MIN_PROBABILITY = 0.2
MAX_SOURCES = 2

SOURCES = {
    "canvas": "Karty na plátně Opory: zadání, spec, bloky, vazby, rozhodnutí a stav práce.",
    "find": "Sémantické hledání v kódu a dokumentaci projektu: kde se řeší určité téma.",
    "code": "LSP: definice, reference a symboly konkrétní funkce, třídy nebo souboru.",
    "graphify": "Graf vztahů souborů a modulů: kdo na koho závisí, komunity, architektura v souvislostech.",
    "memory": "Paměť role agenta: dřívější rozhodnutí, poučení a kontext z minulých sessions.",
    "web": "Web: knihovny, externí API, ceny a dokumentace mimo projekt.",
}

QUESTIONS = {
    "source": {"type": "choice", "instructions": "Který podklad nejlépe pomůže odpovědět na tento požadavek?",
               "criteria": SOURCES},
    "needs_lookup": {"type": "noul",
                     "instructions": "Potřebuje odpověď dohledat podklad v projektu nebo na webu?"},
}


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return None
    return float(value)


def hint_from(answers):
    """Odpovědi Jev → `{sources, needsLookup}`, nebo `None`, když tvar nesedí."""
    if not isinstance(answers, dict):
        return None
    source = answers.get("source") if isinstance(answers.get("source"), dict) else {}
    lookup = answers.get("needs_lookup") if isinstance(answers.get("needs_lookup"), dict) else {}
    needs = _probability(lookup.get("noul"))
    probabilities = source.get("probabilities")
    ranked = []
    if isinstance(probabilities, dict):
        scored = ((name, _probability(value)) for name, value in probabilities.items() if name in SOURCES)
        ranked = sorted(((name, p) for name, p in scored if p is not None and p >= MIN_PROBABILITY),
                        key=lambda item: -item[1])
    if needs is None and not ranked:
        return None
    return {"sources": [name for name, _p in ranked[:MAX_SOURCES]],
            "needsLookup": round(needs, 3) if needs is not None else None}


def route(text, context, *, evaluate):
    """Hint pro zprávu, nebo `None`. Lomítkové příkazy (`/grill-me`) se nesměrují."""
    if not isinstance(text, str) or text.lstrip().startswith("/"):
        return None
    context = context or {}
    state = {"request": text[:MAX_STATE_TEXT], "environment": context.get("environment"),
             "selectedCount": len(context.get("selectedNodeIds") or [])}
    return hint_from(evaluate(state, QUESTIONS))
