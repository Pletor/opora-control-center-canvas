"""Kroky procesu po vrstvách FE / BE / DB / Infra (`docs/navrhy/2026-11-04-platno-procesu.md` §1).

Plátno se nespouští (`run=None`); typy nesou vrstvu, porty a parametry. Texty „kdy použít“ jsou v `guidance.py`.
"""

from backend.flow.node_spec import NodeType, Port

MAIN_IN, MAIN_OUT = Port("main", "in"), Port("main", "out")
BOTH, SOURCE, SINK = (MAIN_IN, MAIN_OUT), (MAIN_OUT,), (MAIN_IN,)
BRANCH = (MAIN_IN, Port("true", "out", label="true"), Port("false", "out", label="false"))


def _t(name, ports, params, trigger=False):
    layer = name.split(".")[0]
    return NodeType(name, 1, ports, None, trigger=trigger, params=params, category=layer, layer=layer)


def _custom_step(params):
    names = [str(b) for b in params.get("branches") or () if str(b)] if isinstance(params.get("branches"), list) else []
    return (MAIN_IN, *(Port(n, "out", label=n) for n in names)) if names else BOTH


PROCESS_TYPES = (
    _t("fe.click", SOURCE, {"label": "popisek tlačítka", "element": "selektor nebo jméno prvku"}, trigger=True),
    _t("fe.form", SOURCE, {"fields": "[{name, type, required}]", "submit": "popisek odeslání"}, trigger=True),
    _t("fe.navigate", BOTH, {"to": "cesta stránky", "replace": "true | false"}),
    _t("fe.state", BOTH, {"key": "jméno stavu", "initial": "výchozí hodnota", "expression": "výraz změny"}),
    _t("fe.show", SINK, {"component": "co se zobrazí", "bind": "výraz dat"}),
    _t("fe.notify", SINK, {"level": "info | success | warning | error", "message": "text"}),
    _t("be.endpoint", BOTH, {"method": "GET | POST | PUT | PATCH | DELETE", "path": "cesta", "body": "schéma těla",
                             "response": "schéma odpovědi"}),
    _t("be.validate", BRANCH, {"conditions": "[{left, operator, right}]", "combinator": "and | or"}),
    _t("be.function", BOTH, {"expression": "výraz výpočtu", "description": "co funkce dělá"}),
    _t("be.middleware", BOTH, {"name": "jméno", "description": "co kontroluje nebo doplňuje"}),
    _t("be.auth", BOTH, {"scheme": "session | token | oauth", "roles": "[role]"}),
    _t("db.read", BOTH, {"table": "tabulka", "columns": "[sloupce]", "where": "podmínka"}),
    _t("db.write", BOTH, {"table": "tabulka", "columns": "[sloupce]", "where": "podmínka (update, delete)"}),
    _t("db.transaction", BOTH, {"table": "tabulky", "columns": "[sloupce]", "where": "podmínka"}),
    _t("infra.api", BOTH, {"method": "GET | POST | …", "url": "adresa", "body": "tělo"}),
    _t("infra.cache", BOTH, {"key": "klíč", "ttlSeconds": "platnost"}),
    _t("infra.queue", BOTH, {"queue": "jméno fronty", "message": "tělo zprávy"}),
    _t("infra.storage", BOTH, {"operation": "read | write", "path": "cesta"}),
    _t("infra.email", BOTH, {"to": "příjemce", "subject": "předmět", "template": "šablona"}),
    # krok na míru (§1b): vrstvu a titulek vyžaduje `graph_check`, větve = jména výstupů jako u Switche
    NodeType("custom.step", 1, BOTH, None, params={"title": "titulek", "description": "co krok dělá",
                                                    "rule": "výraz pro simulaci", "branches": "[jména výstupů]"},
             category="custom", dynamic=_custom_step),
)
