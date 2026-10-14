"""Tabulka disciplín (docs/schranka-neurony.md §2) a její pomocné funkce."""
from backend.editor.brief_vault.brief_vault_disciplines import (
    BY_ID,
    DISCIPLINE_FILTERS,
    DISCIPLINE_IDS,
    DISCIPLINES,
    GROUPS,
    discipline_from_track,
    group_of,
    has_logic_blocks,
    is_discipline,
    layer_of,
    public_table,
    track_from_discipline,
)


def test_table_matches_contract():
    assert DISCIPLINE_IDS == ("cx", "ux", "ui", "content", "fe", "be", "api", "db", "cache", "ai", "security", "data",
                              "test", "infra", "cloud", "devops", "observability")
    assert len(set(DISCIPLINE_IDS)) == len(DISCIPLINES) and all(item.group in GROUPS for item in DISCIPLINES)
    by_group = {group: [item.id for item in DISCIPLINES if item.group == group] for group in GROUPS}
    assert by_group == {"kresleni": ["cx", "ux", "ui", "content"],
                        "logika": ["fe", "be", "api", "db", "cache", "ai", "security", "data", "test"],
                        "provoz": ["infra", "cloud", "devops", "observability"]}
    assert {item.id for item in DISCIPLINES if item.logic_blocks} == {"be", "api", "db", "cache", "ai", "security", "data"}
    assert {key: layer_of(key) for key in DISCIPLINE_IDS} == {
        "cx": "frontend", "ux": "frontend", "ui": "frontend", "content": "frontend", "fe": "frontend",
        "be": "backend", "api": "backend", "db": "database", "cache": "database", "ai": "backend",
        "security": "backend", "data": "backend", "test": "backend",
        "infra": None, "cloud": None, "devops": None, "observability": None}
    assert BY_ID["ai"].label == "AI a agenti (retrieval, paměť, routing)"
    assert DISCIPLINE_FILTERS == (*DISCIPLINE_IDS, "none")


def test_helpers():
    assert is_discipline("db") and not is_discipline("none") and not is_discipline(None) and not is_discipline(["db"])
    assert group_of("ui") == "kresleni" and group_of("test") == "logika" and group_of("cloud") == "provoz"
    assert group_of(None) is None and layer_of("neni") is None
    assert has_logic_blocks("api") and not has_logic_blocks("fe") and not has_logic_blocks(None)


def test_track_migration_and_alias():
    assert [discipline_from_track(value) for value in ("ux", "logic", None, "design", 1)] == ["ux", "be", None, None, None]
    assert [track_from_discipline(value) for value in ("cx", "content", "fe", "be", "devops", None)] == [
        "ux", "ux", "logic", "logic", "logic", None]


def test_public_table():
    table = public_table({"be": 3})
    assert [item["id"] for item in table] == list(DISCIPLINE_IDS)
    assert table[5] == {"id": "be", "group": "logika", "label": "Backend", "layer": "backend", "logicBlocks": True, "live": 3}
    assert all(item["live"] == 0 for item in table if item["id"] != "be")
