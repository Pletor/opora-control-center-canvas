"""Jednotný index plátna: záznamy karet a vazeb, hledání s filtry a pořadí (kontrakt §5)."""

import pytest

from backend.canvas.canvas_index import build_index, search


def item(node_id, name, kind="node", parent_id=None, purpose="", **extra):
    return {"id": node_id, "parentId": parent_id, "kind": kind, "name": name, "purpose": purpose,
            "x": 0, "y": 0, **extra}


GRAPH = {
    "nodes": [
        item("s1", "Editor", "sector", purpose="Úpravy plátna",
             sourceRef={"origin": "existing", "path": "frontend/editor", "kind": "directory"}),
        item("n1", "[task] Pop-up tvorby", parent_id="s1", purpose="Dialog pro novou kartu",
             card={"layer": "frontend", "status": "ready", "due": "2026-10-10"}),
        item("n2", "[research] Žebříček", parent_id="s1"),
        item("n3", "Hotová", parent_id="n1", card={"layer": "library"}),
        item("c1", "Poznámka", "comment", parent_id="s1", purpose="tvorby"),
        item("a1", "", "area", size={"w": 500, "h": 500}),
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "port": "next"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ],
}
STATE = {
    "nodes": {
        "n1": {"phase": "discover", "criteria": [{"id": "k1", "text": "Tlačítko je šedé", "checked": False}],
               "steps": [{"id": "t1", "text": "Napsat formulář", "assignee": "", "done": False}],
               "blocks": [{"id": "b1", "title": "Validace", "text": "missingFields",
                           "todos": [{"id": "td", "text": "Hláška česky"}]}]},
        "n3": {"phase": "discover", "criteria": [], "steps": [],
               "done": {"confirmed": True, "at": "", "by": "human", "note": ""}},
    },
    "edges": {"e1": {"log": "", "summary": "Dialog hotový", "handoff": "Převezmi výzkum", "improvements": "",
                     "errors": "", "updatedAt": "", "by": "agent", "agent": "",
                     "sentAt": "2026-10-02T08:00:00+00:00", "due": "2026-10-12"}},
}


@pytest.fixture
def entries():
    return build_index(GRAPH, STATE)


def by_id(entries):
    return {entry["id"]: entry for entry in entries}


def test_card_entry_has_the_contract_shape(entries):
    entry = by_id(entries)["n1"]
    assert {key: value for key, value in entry.items() if key != "text"} == {
        "id": "n1", "kind": "node", "name": "[task] Pop-up tvorby", "type": "task", "layer": "frontend",
        "status": "ready",
        "due": "2026-10-10", "path": ["Editor", "[task] Pop-up tvorby"], "address": "editor/pop-up-tvorby",
        "parentId": "s1", "sectorId": "s1", "purpose": "Dialog pro novou kartu", "sourcePath": "",
    }
    for part in ("editor/pop-up-tvorby", "task", "FE", "Validace", "Hláška česky", "Tlačítko je šedé", "Napsat formulář"):
        assert part in entry["text"]


def test_comments_are_not_indexed_and_areas_sectors_are(entries):
    rows = by_id(entries)
    assert "c1" not in rows
    assert rows["a1"]["kind"] == "area" and rows["a1"]["address"] == "a1" and rows["a1"]["type"] is None
    assert rows["a1"]["layer"] is None and rows["s1"]["layer"] is None
    sector = rows["s1"]
    assert sector["sectorId"] == "s1" and sector["status"] is None and sector["sourcePath"] == "frontend/editor"
    assert "frontend/editor" in sector["text"]


def test_derived_type_and_status(entries):
    rows = by_id(entries)
    assert rows["n2"]["type"] == "research" and rows["n2"]["address"] == "editor/zebricek"
    assert rows["n2"]["status"] is None and rows["n2"]["due"] is None
    assert rows["n3"]["status"] == "done" and rows["n3"]["address"] == "editor/pop-up-tvorby/hotova"
    assert rows["n3"]["sectorId"] == "s1"


def test_edge_entry_carries_ends_and_report(entries):
    rows = by_id(entries)
    assert {key: value for key, value in rows["e1"].items() if key != "text"} == {
        "id": "e1", "kind": "edge", "port": "next", "from": "n1", "to": "n2",
        "fromName": "[task] Pop-up tvorby", "toName": "[research] Žebříček",
        "fromAddress": "editor/pop-up-tvorby", "toAddress": "editor/zebricek",
        "summary": "Dialog hotový", "handoff": "Převezmi výzkum",
        "sentAt": "2026-10-02T08:00:00+00:00", "due": "2026-10-12",
    }
    assert "Převezmi výzkum" in rows["e1"]["text"]
    assert rows["e2"]["port"] == "next" and rows["e2"]["summary"] == "" and rows["e2"]["sentAt"] == ""


def test_empty_query_returns_everything(entries):
    result = search(entries)
    assert result["total"] == len(entries) == 7


def test_every_word_must_match_without_diacritics_or_case(entries):
    assert [row["id"] for row in search(entries, "HLASKA validace")["entries"]] == ["n1"]
    assert search(entries, "hlaska nic-takoveho")["total"] == 0


def test_filters_are_exact(entries):
    assert [row["id"] for row in search(entries, "typ:task")["entries"]] == ["n1"]
    assert [row["id"] for row in search(entries, "stav:done")["entries"]] == ["n3"]
    assert [row["id"] for row in search(entries, "druh:edge")["entries"]] == ["e1", "e2"]
    assert [row["id"] for row in search(entries, "druh:edge výzkum")["entries"]] == ["e1"]
    assert search(entries, "typ:tas")["total"] == 0


@pytest.mark.parametrize("query, expected", [
    ("vrstva:fe", ["n1"]), ("vrstva:FE", ["n1"]), ("vrstva:frontend", ["n1"]),
    ("vrstva:knihovna", ["n3"]), ("vrstva:library", ["n3"]), ("vrstva:db", []), ("vrstva:be", []),
])
def test_layer_filter_accepts_label_and_full_name(entries, query, expected):
    assert [row["id"] for row in search(entries, query)["entries"]] == expected


def test_layer_label_is_searchable_text(entries):
    assert "n3" in [row["id"] for row in search(entries, "knihovna")["entries"]]


def test_name_match_beats_address_beats_elsewhere(entries):
    ids = [row["id"] for row in search(entries, "tvorby")["entries"]]
    # n1 v názvu; e1 (adresa zdroje editor/pop-up-tvorby) a n3 (editor/pop-up-tvorby/hotova)
    # v adrese, mezi sebou podle adresy; e2 jen jinde v textu (adresa cíle).
    assert ids == ["n1", "e1", "n3", "e2"]


def test_limit(entries):
    result = search(entries, "", 2)
    assert len(result["entries"]) == 2 and result["total"] == 7
    for bad in (0, 2001, "5"):
        with pytest.raises(ValueError):
            search(entries, "", bad)


def test_legacy_graph_and_state_without_new_fields():
    graph = {"nodes": [item("n1", "Stará karta")], "edges": []}
    entries = build_index(graph, {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": []})
    assert entries[0]["type"] is None and entries[0]["layer"] is None and entries[0]["status"] is None and entries[0]["address"] == "stara-karta"
