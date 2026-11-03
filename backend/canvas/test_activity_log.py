"""Záznam činnosti: člověk a agent odděleně, každý zápis dohledatelný (docs/zaznam-cinnosti.md)."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.activity_log import describe, parse_actor

ORIGIN = "http://127.0.0.1:8740"
HUMAN = {"origin": ORIGIN}
AGENT = {"origin": ORIGIN, "x-opora-actor": "agent; name=Claude Code (terminal)"}
SCOPE = {"project": "draft", "workspace": "draft"}
STATE = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": []}


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, ("unknown", "")),
        ("", ("unknown", "")),
        ("agent; name=Claude Code (terminal)", ("agent", "Claude Code (terminal)")),
        ("Agent;name=sonnet-1.0", ("agent", "sonnet-1.0")),
        ("agent", ("agent", "agent")),
        ("agent; name=<script>", ("agent", "agent")),
        ("robot; name=x", ("unknown", "")),
    ],
)
def test_parse_actor(header, expected):
    assert parse_actor(header) == expected


def test_describe_takes_scope_nodes_and_operation_but_no_text():
    body = json.dumps({**SCOPE, "nodeId": "n1", "expectedRevision": 3,
                       "op": {"kind": "update", "patch": {"text": "tajné zadání"}}}).encode()
    described = describe(body, {})
    assert described == {"project": "draft", "workspace": "draft", "nodeIds": ["n1"],
                         "summary": "expectedRevision,nodeId,op op=update"}
    assert "tajné" not in described["summary"]
    assert describe(b"not json", {"project": "p1"})["project"] == "p1"


def test_human_and_agent_writes_are_logged_apart(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert client.post("/api/desktop-v3/state", headers=HUMAN,
                           json={**SCOPE, "expectedRevision": 0, "state": STATE}).status_code == 200
        refused = client.post("/api/desktop-v3/state", headers=AGENT,
                              json={**SCOPE, "expectedRevision": 0, "state": STATE})
        assert refused.status_code == 409  # i neúspěšný zápis je dohledatelný
        client.get("/api/desktop-v3/state", params=SCOPE)  # čtení se nezapisuje

        human = client.get("/api/activity-log", params={**SCOPE, "actor": "human"}).json()["entries"]
        agent = client.get("/api/activity-log", params={**SCOPE, "actor": "agent"}).json()["entries"]
        both = client.get("/api/activity-log", params=SCOPE).json()["entries"]

    assert [(e["path"], e["status"], e["agent"]) for e in human] == [("/api/desktop-v3/state", 200, "")]
    assert [(e["path"], e["status"], e["agent"]) for e in agent] == [
        ("/api/desktop-v3/state", 409, "Claude Code (terminal)")
    ]
    assert [e["actor"] for e in both] == ["agent", "human"]  # nejnovější první


def test_paging_and_node_filter(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        for node in ("a", "b", "a"):
            client.post("/api/desktop-v3/agent-workspace", headers=AGENT,
                        json={**SCOPE, "nodeId": node, "expectedRevision": 0, "sections": {}, "by": "agent"})
        first = client.get("/api/activity-log", params={"limit": 2}).json()
        second = client.get("/api/activity-log", params={"limit": 2, "before": first["nextBefore"]}).json()
        only_a = client.get("/api/activity-log", params={"nodeId": "a"}).json()["entries"]
        bad = client.get("/api/activity-log", params={"actor": "robot"})
    assert len(first["entries"]) == 2 and first["nextBefore"] is not None
    assert len(second["entries"]) == 1 and second["nextBefore"] is None
    assert [e["nodeIds"] for e in only_a] == [["a"], ["a"]]
    assert bad.status_code == 409


def test_agent_and_time_range_filter_heart_steps_of_one_batch(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        db = app.state.service.db
        rows = [("2026-10-31T09:59:59.500000+00:00", "heart"), ("2026-10-31T10:00:00+00:00", "heart"),
                ("2026-10-31T10:00:30.250000+00:00", "Claude Code (terminal)"),
                ("2026-10-31T10:01:00.100000+00:00", "heart"), ("2026-10-31T10:02:01+00:00", "heart")]
        for at, agent in rows:
            db.execute("INSERT INTO activity_log(at,actor,agent,method,path,project_id,workspace_id,node_ids,"
                       "status,summary) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (at, "agent", agent, "POST", "/api/gate/requests", "draft", "draft", "[]", 201, ""))
        db.commit()
        since = client.get("/api/activity-log", params={**SCOPE, "agent": "heart",
                                                         "since": "2026-10-31T10:00:00Z"}).json()["entries"]
        batch = client.get("/api/activity-log", params={**SCOPE, "agent": "heart", "since": "2026-10-31T10:00:00Z",
                                                         "until": "2026-10-31T11:01:30+01:00"}).json()["entries"]
        bad = client.get("/api/activity-log", params={"since": "včera"})
    assert [e["at"][11:19] for e in since] == ["10:02:01", "10:01:00", "10:00:00"]
    assert [e["at"][11:19] for e in batch] == ["10:01:00", "10:00:00"]
    assert bad.status_code == 409
