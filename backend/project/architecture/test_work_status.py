from datetime import UTC, datetime, timedelta

import pytest

from backend.project.architecture.work_status import (
    CARD_ACTIVITY_SECONDS,
    STOPPED_WINDOW_SECONDS,
    compose_work_status,
    worktree_state,
)

NOW = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)


def ago(seconds):
    return (NOW - timedelta(seconds=seconds)).isoformat()


def session(state):
    return {"id": "s", "workspace": "w1", "state": state}


def lease(expires_in=600):
    return {"workspace_id": "w1", "node_id": "c1", "expires_at": NOW.timestamp() + expires_in}


def act(seconds):
    return {"c1": {"updated_at": ago(seconds)}}


CASES = [
    ("nic", [], [], {}, "none"),
    ("asistent běží", [session("running")], [], {}, "running"),
    ("asistent čeká na schválení", [session("waiting_approval")], [], {}, "waiting"),
    ("asistent idle (i po restartu)", [session("idle")], [], {}, "waiting"),
    ("asistent error", [session("error")], [], {}, "stopped"),
    ("zavřená relace se nepočítá", [session("closed")], [], {}, "none"),
    ("lease + čerstvá aktivita", [], [lease()], act(CARD_ACTIVITY_SECONDS), "running"),
    ("lease + stará aktivita", [], [lease()], act(CARD_ACTIVITY_SECONDS + 1), "waiting"),
    ("lease bez aktivity", [], [lease()], {}, "waiting"),
    ("prošlá lease s aktivitou < 24 h", [], [lease(-5)], act(3600), "stopped"),
    ("prošlá lease s aktivitou na hraně", [], [lease(-5)], act(STOPPED_WINDOW_SECONDS), "stopped"),
    ("prošlá lease se starou aktivitou", [], [lease(-5)], act(STOPPED_WINDOW_SECONDS + 1), "none"),
    ("prošlá lease bez aktivity", [], [lease(-5)], {}, "none"),
    ("přednost: běží přebije stojí", [session("error")], [lease()], act(5), "running"),
    ("přednost: čeká přebije stojí", [session("idle")], [lease(-5)], act(10), "waiting"),
    ("přednost: stojí přebije bez relace", [], [lease(-5)], act(10), "stopped"),
    ("přednost: lease běží přebije čeká", [session("idle")], [lease()], act(5), "running"),
]


@pytest.mark.parametrize("label,sessions,leases,activity,expected", CASES, ids=[c[0] for c in CASES])
def test_worktree_state_table(label, sessions, leases, activity, expected):
    state, reasons = worktree_state(sessions, leases, activity, NOW)
    assert state == expected
    assert bool(reasons) == (expected != "none")


def test_reasons_come_from_winning_level_only():
    state, reasons = worktree_state([session("running"), session("error")], [], {}, NOW)
    assert (state, reasons) == ("running", ["asistent běží"])


def test_missing_session_is_none_never_stopped():
    assert worktree_state([], [], {}, NOW) == ("none", [])


DOMAINS = [
    {"id": "prod", "name": "Aplikace", "environment": {"name": "Produkce", "host": "app.example.cz"}},
    {"id": "dev", "name": "Aplikace", "environment": {"name": "Vývoj", "host": "app.example.dev"}},
]


def test_domain_grouping_counts_and_unassigned():
    workspaces = [
        {"id": "w1", "node_id": "prod", "branch": "work/w1", "actor": "a"},
        {"id": "w2", "node_id": "prod", "branch": "work/w2", "actor": "b"},
        {"id": "w3", "node_id": "dev", "branch": "work/w3", "actor": "c"},
        {"id": "w4", "node_id": "project", "branch": "work/w4", "actor": "01-start-projektu"},
        {"id": "w5", "node_id": "page-in-domain", "branch": "work/w5", "actor": "d"},
    ]
    sources = {
        "sessions": [
            {"id": "s1", "workspace": "w1", "state": "running", "nodeId": "c1", "updatedAt": ago(5)},
            {"id": "s2", "workspace": "main", "state": "idle", "nodeId": None, "updatedAt": ago(5)},
            {"id": "s3", "workspace": "draft", "state": "running", "nodeId": None, "updatedAt": ago(5)},
        ],
        "leases": [{"workspace_id": "w2", "node_id": "c9", "owner": "x", "expires_at": NOW.timestamp() + 60}],
        "activity": [],
    }
    result = compose_work_status(DOMAINS, workspaces, sources, NOW, lambda wid, node: f"Karta {node}")
    prod, dev = result["domains"]
    assert prod["counts"] == {"running": 1, "waiting": 1, "stopped": 0, "none": 0, "total": 2}
    assert dev["counts"] == {"running": 0, "waiting": 0, "stopped": 0, "none": 1, "total": 1}
    assert prod["environment"] == {"name": "Produkce", "host": "app.example.cz"}
    assert [w["id"] for w in result["unassigned"]] == ["w4", "w5"]
    assert result["unassigned"][0]["state"] == "none"
    assert prod["worktrees"][0]["cards"] == [{"nodeId": "c1", "name": "Karta c1"}]
    assert prod["worktrees"][1]["cards"] == [{"nodeId": "c9", "name": "Karta c9"}]
    assert prod["worktrees"][0]["sessions"][0]["source"] == "assistant"
    assert "createdAt" not in prod["worktrees"][0]
    assert [s["id"] for s in result["mainSessions"]] == ["s2", "s3"]


def test_created_at_is_passed_through_when_stored():
    sources = {"sessions": [], "leases": [], "activity": []}
    result = compose_work_status(DOMAINS, [{"id": "w1", "node_id": "dev", "created_at": "2026-10-01"}], sources, NOW)
    assert result["domains"][1]["worktrees"][0]["createdAt"] == "2026-10-01"
