"""Disciplíny (neurony) Schránky: jediný zdroj tabulky z docs/schranka-neurony.md §2.

Každý fragment patří právě jedné disciplíně (`discipline`); NULL = dědí od předka. Zrcadlo tabulky
na frontendu je `frontend/editor/brief-vault-dock/logic/disciplines.ts` (kontroluje shodu s
`GET /api/brief-vault/disciplines`). Skupina určuje oblast plánu, `layer` je `card.layer` karty
(None = provoz bez vrstvy), `logic_blocks` = karta dostane 4 závěrečné bloky logiky.
"""

from typing import NamedTuple

GROUPS = ("kresleni", "logika", "provoz")
GROUP_LABELS = {"kresleni": "Kreslení", "logika": "Logika", "provoz": "Provoz"}


class Discipline(NamedTuple):
    id: str
    group: str
    label: str
    layer: str | None
    logic_blocks: bool


DISCIPLINES = (
    Discipline("cx", "kresleni", "CX (zkušenost zákazníka)", "frontend", False),
    Discipline("ux", "kresleni", "UX (tok, obrazovky, stavy)", "frontend", False),
    Discipline("ui", "kresleni", "UI (vzhled, komponenty)", "frontend", False),
    Discipline("content", "kresleni", "Obsah a texty", "frontend", False),
    Discipline("fe", "logika", "Frontend (implementace)", "frontend", False),
    Discipline("be", "logika", "Backend", "backend", True),
    Discipline("api", "logika", "API a kontrakty", "backend", True),
    Discipline("db", "logika", "Databáze a datový model", "database", True),
    Discipline("cache", "logika", "Cache", "database", True),
    Discipline("ai", "logika", "AI a agenti (retrieval, paměť, routing)", "backend", True),
    Discipline("security", "logika", "Bezpečnost a soukromí", "backend", True),
    Discipline("data", "logika", "Data a analytika", "backend", True),
    Discipline("test", "logika", "Testy, QA, evaly", "backend", False),
    Discipline("infra", "provoz", "Infrastruktura", None, False),
    Discipline("cloud", "provoz", "Cloud", None, False),
    Discipline("devops", "provoz", "CI/CD a nasazení", None, False),
    Discipline("observability", "provoz", "Logy, metriky, trasování", None, False),
)
BY_ID = {item.id: item for item in DISCIPLINES}
DISCIPLINE_IDS = tuple(BY_ID)
# Filtr stromu: id disciplíny nebo `none` = nezařazené (bez disciplíny na celé cestě ke kořeni).
DISCIPLINE_FILTERS = (*DISCIPLINE_IDS, "none")
# Migrace stop (§2 „Migrace“): `track` → `discipline`. Stejné zobrazení používá backfill DB i snímky verzí.
TRACK_TO_DISCIPLINE = {"ux": "ux", "logic": "be"}


def is_discipline(value):
    return isinstance(value, str) and value in BY_ID


def group_of(discipline):
    """Skupina disciplíny (`kresleni` | `logika` | `provoz`), None pro nezařazené."""
    return BY_ID[discipline].group if discipline in BY_ID else None


def layer_of(discipline):
    """`card.layer` karty disciplíny; None pro provoz i nezařazené."""
    return BY_ID[discipline].layer if discipline in BY_ID else None


def has_logic_blocks(discipline):
    return discipline in BY_ID and BY_ID[discipline].logic_blocks


def discipline_from_track(track):
    """Stará stopa → disciplína (`ux` → `ux`, `logic` → `be`, cokoli jiného → None)."""
    return TRACK_TO_DISCIPLINE.get(track) if isinstance(track, str) else None


def public_table(live_counts=None):
    """Tabulka pro `GET /api/brief-vault/disciplines`; `live_counts` = {id: počet živých fragmentů}."""
    live_counts = live_counts or {}
    return [{"id": item.id, "group": item.group, "label": item.label, "layer": item.layer,
             "logicBlocks": item.logic_blocks, "live": live_counts.get(item.id, 0)} for item in DISCIPLINES]
