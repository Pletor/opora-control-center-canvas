"""Porty bloku, uzavření karty a zprávy agenta na vazbách.

Všechny tři klíče jsou volitelné: starší uložený stav bez nich zůstává platný a čte se
s výchozími hodnotami. Agent smí uzavření jen navrhnout, potvrzení patří člověku.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.desktop_v3_state import (
    MAX_PORTS,
    default_done,
    default_state,
    fill_defaults,
    validate_state,
)

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
LEGACY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": []}


def branch(kind="none", target="", note=""):
    return {"kind": kind, "targetId": target, "note": note}


def block(bid="b1", number="1", **overrides):
    item = {
        "id": bid, "number": number, "title": f"Blok {number}", "text": "", "tags": [], "todos": [], "images": [],
        "state": {"status": "open", "condition": "", "onMet": branch(), "onUnmet": branch()},
        "parentBlockId": "",
    }
    item.update(overrides)
    return item


def report(**overrides):
    item = {
        "log": "Založil jsem test.", "summary": "Test běží.", "handoff": "Pokračuj u routeru.",
        "improvements": "Chybí fixture.", "errors": "", "updatedAt": "2026-09-14T08:00:00+00:00",
        "by": "agent", "agent": "sonnet/impl",
    }
    item.update(overrides)
    return item


def state(node=None, edges=None):
    value = copy.deepcopy(LEGACY)
    if node is not None:
        value["nodes"] = {"focus": node}
    if edges is not None:
        value["edges"] = edges
    return value


def node(**overrides):
    item = {"phase": "discover", "criteria": [], "steps": []}
    item.update(overrides)
    return item


# ---- porty bloku ------------------------------------------------------------------


def test_block_ports_are_accepted_and_legacy_block_without_ports_stays_valid():
    with_ports = block(ports=[{"id": "p1", "label": "Návrh API"}, {"id": "p2", "label": ""}])
    accepted = validate_state(state(node(blocks=[with_ports, block("b2", "2")])))
    assert accepted["nodes"]["focus"]["blocks"][0]["ports"][0]["label"] == "Návrh API"
    assert "ports" not in accepted["nodes"]["focus"]["blocks"][1]


@pytest.mark.parametrize(
    "ports",
    [
        [{"id": f"p{i}", "label": "x"} for i in range(MAX_PORTS + 1)],
        [{"id": "p1", "label": "a"}, {"id": "p1", "label": "b"}],
        [{"id": "p1", "label": "x" * 81}],
        [{"id": "p1", "label": 5}],
        [{"id": "p1"}],
        [{"id": "p1", "label": "x", "target": "b2"}],
        [{"id": "ne platné!", "label": "x"}],
        {"p1": "x"},
    ],
)
def test_invalid_ports_are_rejected(ports):
    with pytest.raises(ValueError):
        validate_state(state(node(blocks=[block(ports=ports)])))


def test_exactly_eight_ports_still_fit():
    ports = [{"id": f"p{i}", "label": f"Port {i}"} for i in range(MAX_PORTS)]
    assert len(validate_state(state(node(blocks=[block(ports=ports)])))["nodes"]["focus"]["blocks"][0]["ports"]) == 8


# ---- uzavření karty ---------------------------------------------------------------


def test_done_is_optional_and_human_may_confirm_it():
    assert "done" not in validate_state(state(node()))["nodes"]["focus"]
    closed = {"confirmed": True, "at": "2026-09-14T08:00:00+00:00", "by": "human", "note": "Hotovo."}
    assert validate_state(state(node(done=closed)))["nodes"]["focus"]["done"] == closed
    assert validate_state(state(node(done=default_done())))["nodes"]["focus"]["done"] == default_done()


def test_stored_done_may_be_confirmed_by_agent():
    """Plná autonomie (docs/plna-autonomie-agenta.md §6): tvar uloženého stavu přijme potvrzení od agenta;
    kdo smí potvrdit, hlídá brána při zápisu (backend/app/test_full_autonomy.py)."""
    proposal = {"confirmed": False, "at": "2026-09-14T08:00:00+00:00", "by": "agent", "note": "Podle mě hotovo."}
    assert validate_state(state(node(done=proposal)))["nodes"]["focus"]["done"] == proposal
    confirmed = {**proposal, "confirmed": True}
    assert validate_state(state(node(done=confirmed)))["nodes"]["focus"]["done"] == confirmed


@pytest.mark.parametrize(
    "done",
    [
        {"confirmed": "ano", "at": "", "by": "human", "note": ""},
        {"confirmed": False, "at": "včera", "by": "human", "note": ""},
        {"confirmed": False, "at": "", "by": "robot", "note": ""},
        {"confirmed": False, "at": "", "by": "human", "note": "x" * 4001},
        {"confirmed": False, "at": "", "by": "human"},
        {"confirmed": False, "at": "", "by": "human", "note": "", "extra": 1},
        [],
    ],
)
def test_invalid_done_is_rejected(done):
    with pytest.raises(ValueError):
        validate_state(state(node(done=done)))


# ---- zprávy na vazbách ------------------------------------------------------------


def test_default_state_has_empty_edges_and_legacy_state_reads_with_them():
    assert default_state()["edges"] == {}
    assert fill_defaults(copy.deepcopy(LEGACY))["edges"] == {}
    assert validate_state(copy.deepcopy(LEGACY)) == LEGACY


def test_edge_reports_are_accepted_even_when_the_edge_is_gone_from_the_graph():
    value = state(edges={"smazana-vazba": report()})
    assert validate_state(value)["edges"]["smazana-vazba"]["summary"] == "Test běží."


@pytest.mark.parametrize(
    "edges",
    [
        {"e1": report(log="x" * 4001)},
        {"e1": report(errors=5)},
        {"e1": report(by="robot")},
        {"e1": report(agent="a" * 121)},
        {"e1": report(updatedAt="včera")},
        {"e1": {**report(), "extra": 1}},
        {"e1": {key: "" for key in ("log", "summary", "handoff", "improvements", "errors")}},
        {"ne platné!": report()},
        {"e1": []},
        [],
    ],
)
def test_invalid_edge_reports_are_rejected(edges):
    with pytest.raises(ValueError):
        validate_state(state(edges=edges))


def test_empty_texts_and_empty_timestamp_are_a_valid_report():
    blank = report(log="", summary="", handoff="", improvements="", errors="", updatedAt="", agent="", by="human")
    assert validate_state(state(edges={"e1": blank}))["edges"]["e1"] == blank


@pytest.mark.parametrize(
    "extra",
    [
        {"sentAt": "2026-10-02T08:00:00+00:00"},
        {"sentAt": ""},
        {"due": "2026-10-10"},
        {"due": ""},
        {"sentAt": "2026-10-02T08:00:00+00:00", "due": "2026-10-10"},
    ],
)
def test_report_may_carry_sent_at_and_due(extra):
    value = report(**extra)
    assert validate_state(state(edges={"e1": value}))["edges"]["e1"] == value


@pytest.mark.parametrize(
    "extra",
    [
        {"sentAt": "včera"},
        {"sentAt": None},
        {"due": "2026-02-30"},
        {"due": "10.10.2026"},
        {"due": None},
        {"due": "2026-10-10T08:00"},
    ],
)
def test_invalid_sent_at_or_due_is_rejected(extra):
    with pytest.raises(ValueError):
        validate_state(state(edges={"e1": report(**extra)}))


def test_sent_at_does_not_replace_required_report_keys():
    partial = {key: value for key, value in report(sentAt="").items() if key != "agent"}
    with pytest.raises(ValueError):
        validate_state(state(edges={"e1": partial}))


# ---- přes API ---------------------------------------------------------------------


def _seed_graph(client):
    view = client.get("/api/view", params=SCOPE).json()
    graph = {
        "nodes": [
            {"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
            {"id": "dalsi", "parentId": None, "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0},
        ],
        "edges": [{"id": "e1", "source": "focus", "target": "dalsi", "port": "block",
                   "sourceBlockId": "b1", "sourcePortId": "p1"}],
    }
    assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200


def test_ports_done_and_edge_reports_survive_save_and_reload(tmp_path):
    root = tmp_path / "data"
    value = state(
        node(blocks=[block(ports=[{"id": "p1", "label": "Návrh API"}])], done=default_done()),
        edges={"e1": report()},
    )
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        _seed_graph(client)
        saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": 0, "state": value})
        assert saved.status_code == 200, saved.text
        assert saved.json() == {"revision": 1, "state": value, "readOnly": False}
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["state"] == value


def test_legacy_state_without_edges_reads_back_with_the_empty_section(tmp_path):
    root = tmp_path / "data"
    legacy = copy.deepcopy(LEGACY)
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        assert client.post("/api/desktop-v3/state", headers=HEADERS,
                           json={**SCOPE, "expectedRevision": 0, "state": legacy}).status_code == 200
        reloaded = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert reloaded["revision"] == 1 and reloaded["state"]["edges"] == {}
