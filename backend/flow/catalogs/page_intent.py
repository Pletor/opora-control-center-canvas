"""Katalog uzlů záměru stránky (`kind = page_intent`, kontrakt `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §2).

Záměr se nespouští, typy nemají funkci (`run=None`). Vazby `main` tvoří tok uživatele, vazby `data` tok dat;
`graph_check` hlídá, že `main` vede jen mezi porty `main`, `data` jen mezi porty `data`, a že graf má aspoň jeden
`intent.entry` a jeden `intent.done` (`REQUIRED_TYPES`). `params` popisuje parametry uzlu pro editor.
"""

from backend.flow.node_spec import NodeType, Port

MAIN_IN, MAIN_OUT = Port("main", "in"), Port("main", "out")
DATA = (Port("data", "in", "data"), Port("data", "out", "data"))


def _intent(name, ports, params):
    return NodeType(f"intent.{name}", 1, ports + DATA, None, params=params)


INTENT_TYPES = {
    t.type: t
    for t in (
        _intent("entry", (MAIN_OUT,), {"from": "stránka, odkaz nebo kampaň", "actor": "kdo přichází"}),
        _intent("view", (MAIN_IN, MAIN_OUT), {"section": "id sekce stránky", "shows": "co uživatel vidí"}),
        _intent("action", (MAIN_IN, MAIN_OUT),
                {"do": "open | click | type | submit", "section": "id sekce stránky", "text": "volitelný text"}),
        _intent("reaction", (MAIN_IN, MAIN_OUT),
                {"does": "show | navigate | send_email | store | call", "expect": "ověřitelný popis odpovědi"}),
        _intent("data", (MAIN_IN, MAIN_OUT), {"fields": "[{name, type, required}]", "to": "kam data jdou"}),
        _intent("done", (MAIN_IN,), {"claim": "ověřitelné tvrzení", "check": "visible | path | request | email | record"}),
        _intent("error", (MAIN_IN, MAIN_OUT), {"when": "kdy chyba nastane", "shows": "co uživatel uvidí"}),
    )
}

REQUIRED_TYPES = ("intent.entry", "intent.done")
