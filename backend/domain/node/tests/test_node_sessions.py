import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.domain.node.node_session_sources import (
    ClaudeLaneSource,
    HermesSessionSource,
    SourceError,
    default_process_create_time,
)
from backend.domain.node.node_sessions import NodeSessions, create_node_sessions_router
from backend.domain.service import CanvasService

T0 = datetime(2026, 9, 11, 12, 0, 0, tzinfo=UTC)
HERMES_ID = "20260101_000000_abcdef12"
CLAUDE_ID = "11111111-2222-3333-4444-555555555555"
FORBIDDEN = ("SECRET", "system_prompt", "user_id", "rm -rf", "reasoning-text", "tool-output", "sk-live")


class Clock:
    def __init__(self, moment=T0):
        self.moment = moment

    def __call__(self):
        return self.moment


class FakeHermes:
    def __init__(self, service=None):
        self.service = service
        self.calls = []
        self.session = {
            "id": HERMES_ID, "source": "telegram", "model": "gpt-test", "started_at": (T0 - timedelta(days=1)).timestamp(),
            "ended_at": None, "message_count": 10, "tool_call_count": 3, "input_tokens": 1200,
            "output_tokens": 300, "actual_cost_usd": 0.42, "estimated_cost_usd": 0.0, "parent_session_id": None,
            "user_id": "tg-SECRET", "system_prompt": "SECRET prompt", "model_config": {"k": "SECRET"},
        }
        self.messages = {}
        self.fail = None

    def __call__(self, path):
        if self.service is not None:
            assert not self.service.lock._is_owned(), "síťové čtení pod service.lock"
        self.calls.append(path)
        if self.fail == "raise":
            raise RuntimeError("SECRET boom")
        if self.fail:
            return self.fail, None
        if path == f"/api/sessions/{HERMES_ID}":
            return 200, {"object": "hermes.session", "session": dict(self.session)}
        if path.startswith(f"/api/sessions/{HERMES_ID}/messages?"):
            query = dict(part.split("=") for part in path.split("?", 1)[1].split("&"))
            offset = int(query["offset"])
            data = [self.messages[i] for i in range(offset, offset + int(query["limit"])) if i in self.messages]
            return 200, {"object": "list", "session_id": HERMES_ID, "data": data,
                         "pagination": {"limit": 50, "offset": offset, "order": "oldest", "returned": len(data)}}
        return 404, None


@pytest.fixture
def service(tmp_path):
    svc = CanvasService(tmp_path / "data")
    graph = {
        "nodes": [
            {"id": "sec1", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
            {"id": "n1", "parentId": "sec1", "kind": "node", "name": "Pracovní panel", "purpose": "", "x": 1, "y": 1},
            {"id": "n2", "parentId": "sec1", "kind": "node", "name": "Jiný uzel", "purpose": "", "x": 2, "y": 2},
        ],
        "edges": [],
    }
    svc.save_graph("draft", "draft", graph, svc.view("draft", "draft")["digest"])
    yield svc
    svc.close()


@pytest.fixture
def lanes(tmp_path):
    root = tmp_path / "lanes"
    root.mkdir()
    return root


def write_lane(root, lane, state=None, events=()):
    directory = root / lane
    directory.mkdir(exist_ok=True)
    if state is not None:
        (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
    with (directory / "events.jsonl").open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write((event if isinstance(event, str) else json.dumps(event)) + "\n")
    return directory


def observed(offset_seconds):
    return (T0 + timedelta(seconds=offset_seconds)).isoformat()


def claude_events(session_id=CLAUDE_ID):
    return [
        {"type": "system", "subtype": "init", "session_id": session_id, "model": "claude-test",
         "cwd": "C:/SECRET", "tools": ["Bash"], "_observedAt": observed(1)},
        {"type": "assistant", "session_id": session_id, "_observedAt": observed(2), "message": {"content": [
            {"type": "thinking", "thinking": "reasoning-text"},
            {"type": "text", "text": "SECRET answer"},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "rm -rf SECRET"}},
            {"type": "tool_use", "id": "t2", "name": "mcp__evil__SECRET", "input": {}},
        ]}},
        {"type": "user", "session_id": session_id, "_observedAt": observed(3), "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "tool-output SECRET", "is_error": False},
            {"type": "tool_result", "tool_use_id": "t2", "content": "tool-output", "is_error": True},
        ]}},
        {"type": "result", "subtype": "success", "is_error": False, "session_id": session_id,
         "result": "SECRET final", "usage": {"input_tokens": 50, "output_tokens": 20},
         "total_cost_usd": 0.07, "_observedAt": observed(4)},
    ]


def running_state(**overrides):
    state = {"sessionId": CLAUDE_ID, "modelAlias": "opus", "pid": 4242, "pidCreatedAt": 1_700_000_000.0,
             "running": True, "startedAt": observed(0), "finishedAt": None, "localTreeInactive": False,
             "exitCode": None, "finishReason": None, "success": None}
    state.update(overrides)
    return state


def make(service, lanes_root=None, *, hermes_fetch=None, create_time=None, clock=None):
    hermes = HermesSessionSource(fetch=hermes_fetch or FakeHermes(service))
    claude = ClaudeLaneSource(lanes_root, process_create_time=create_time or (lambda pid: None))
    return NodeSessions(service, hermes=hermes, claude=claude, clock=clock or Clock())


def payload(**overrides):
    body = {"project": "draft", "workspace": "draft", "nodeId": "n1", "source": "hermes", "sessionId": HERMES_ID,
            "runId": None, "role": "orchestrator", "title": "Telegram orchestrace", "parentSessionId": None,
            "confirmed": True}
    body.update(overrides)
    return body


def assert_safe(data):
    dumped = json.dumps(data, ensure_ascii=False)
    for needle in FORBIDDEN:
        assert needle not in dumped


def test_hermes_bind_stores_baseline_and_hides_prior_history(service):
    fake = FakeHermes(service)
    fake.messages = {i: {"id": i, "session_id": HERMES_ID, "role": "user", "content": "SECRET old task",
                         "timestamp": (T0 - timedelta(hours=1)).timestamp()} for i in range(10)}
    sessions = make(service, hermes_fetch=fake)
    result = sessions.bind(payload())
    assert result["status"] == "idle" and result["events"] == [] and result["model"] == "gpt-test"
    assert result["nodeName"] == "Pracovní panel" and result["sourceAvailable"] is True
    assert result["metrics"] == {"inputTokens": 1200, "outputTokens": 300, "costUsd": 0.42}
    assert "celou session" in result["sourceLabel"]
    listed = sessions.list("draft", "draft", "n1")
    assert listed["limit"] == 100 and listed["truncated"] is False and listed["nodeId"] == "n1"
    assert [s["id"] for s in listed["sessions"]] == [result["id"]]
    assert not any("/messages" in call for call in fake.calls)
    assert_safe(listed)


def test_hermes_new_tool_metadata_after_baseline_only(service):
    fake = FakeHermes(service)
    clock = Clock()
    sessions = make(service, hermes_fetch=fake, clock=clock)
    sessions.bind(payload())
    fake.session["message_count"] = 14
    fake.messages = {
        10: {"id": 10, "session_id": HERMES_ID, "role": "user", "content": "SECRET",
             "timestamp": (T0 - timedelta(hours=2)).timestamp()},
        11: {"id": 11, "session_id": HERMES_ID, "role": "assistant", "content": "SECRET", "reasoning": "reasoning-text",
             "tool_calls": [{"function": {"name": "terminal", "arguments": "rm -rf SECRET"}},
                            {"function": {"name": "SECRET_custom_tool"}}],
             "timestamp": (T0 + timedelta(seconds=5)).timestamp()},
        12: {"id": 12, "session_id": HERMES_ID, "role": "tool", "tool_name": "terminal", "content": "tool-output",
             "timestamp": (T0 + timedelta(seconds=6)).timestamp()},
        13: {"id": 13, "session_id": "other", "role": "user", "content": "SECRET foreign",
             "timestamp": (T0 + timedelta(seconds=7)).timestamp()},
    }
    clock.moment = T0 + timedelta(seconds=30)
    session = sessions.list("draft", "draft", "n1")["sessions"][0]
    assert f"/api/sessions/{HERMES_ID}/messages?limit=50&offset=10" in fake.calls
    assert [e["summary"] for e in session["events"]] == [
        "Volání nástroje: terminal", "Volání nástroje (neuvedený nástroj)", "Nástroj dokončen: terminal"]
    assert len({e["id"] for e in session["events"]}) == len(session["events"])
    assert session["status"] == "recent_activity" and "neprokazuje" in session["statusReason"]
    assert session["lastActivityAt"] == (T0 + timedelta(seconds=6)).isoformat()
    assert_safe(session)
    clock.moment = T0 + timedelta(hours=1)
    assert sessions.list("draft", "draft")["sessions"][0]["status"] == "idle"


def test_hermes_bounded_tail_and_never_running(service):
    fake = FakeHermes(service)
    sessions = make(service, hermes_fetch=fake)
    sessions.bind(payload())
    fake.session["message_count"] = 500
    fake.session["ended_at"] = (T0 + timedelta(minutes=5)).timestamp()
    session = sessions.list("draft", "draft", "n1")["sessions"][0]
    assert f"/api/sessions/{HERMES_ID}/messages?limit=50&offset=450" in fake.calls
    assert session["status"] == "completed" and "nepotvrzuje dokončení projektu" in session["statusReason"]
    fake.session["message_count"] = 3
    fake.session["ended_at"] = None
    assert sessions.list("draft", "draft", "n1")["sessions"][0]["status"] == "unknown"


@pytest.mark.parametrize("change", [
    {"runId": "lane"}, {"confirmed": False}, {"sessionId": "../etc"}, {"sessionId": "a/b"},
    {"nodeId": "missing"}, {"nodeId": "../n1"}, {"source": "other"}, {"role": "boss"}, {"title": " "},
    {"parentSessionId": HERMES_ID}, {"workspace": "x/y"},
])
def test_bind_rejects_invalid_payload_without_persisting(service, change):
    fake = FakeHermes(service)
    sessions = make(service, hermes_fetch=fake)
    with pytest.raises(ValueError):
        sessions.bind(payload(**change))
    assert sessions.list("draft", "draft")["sessions"] == []


def test_bind_rejects_extra_fields_and_unverified_sessions(service):
    fake = FakeHermes(service)
    sessions = make(service, hermes_fetch=fake)
    with pytest.raises(ValueError):
        sessions.bind({**payload(), "extra": 1})
    with pytest.raises(ValueError, match="neexistuje"):
        sessions.bind(payload(sessionId="20260101_000000_ffffffff"))
    fake.session["id"] = "somethingelse"
    with pytest.raises(ValueError, match="jinou session"):
        sessions.bind(payload())
    assert sessions.list("draft", "draft")["sessions"] == []


def test_bind_rejects_readonly_main(service, monkeypatch):
    sessions = make(service)
    original = service.view
    monkeypatch.setattr(service, "view", lambda pid, wid: {**original("draft", "draft"), "readOnly": True})
    with pytest.raises(ValueError, match="pouze pro čtení"):
        sessions.bind(payload())


def test_bind_idempotent_and_conflict_does_not_mutate(service):
    fake = FakeHermes(service)
    sessions = make(service, hermes_fetch=fake)
    first = sessions.bind(payload())
    fake.session["message_count"] = 99
    again = sessions.bind(payload())
    assert again["id"] == first["id"] and again["boundAt"] == first["boundAt"]
    for change in ({"title": "Jiný"}, {"nodeId": "n2"}, {"role": "worker"}):
        with pytest.raises(ValueError, match="nelze přepsat"):
            sessions.bind(payload(**change))
    row = service.db.execute("SELECT node_id,title,role,baseline_cursor FROM node_sessions").fetchall()
    assert [tuple(r) for r in row] == [("n1", "Telegram orchestrace", "orchestrator", 10)]


def test_claude_bind_requires_identity_evidence(service, lanes):
    write_lane(lanes, "opus-backend", running_state(), claude_events())
    write_lane(lanes, "no-evidence", None, [])
    write_lane(lanes, "mismatch", running_state(sessionId="99999999-0000-0000-0000-000000000000"), claude_events())
    sessions = make(service, lanes)
    worker = payload(source="claude", runId="opus-backend", sessionId=CLAUDE_ID, role="worker",
                     title="Opus backend", parentSessionId=HERMES_ID)
    for lane in ("no-evidence", "mismatch", "missing-lane"):
        with pytest.raises(ValueError, match="nelze ověřit"):
            sessions.bind({**worker, "runId": lane})
    with pytest.raises(ValueError):
        sessions.bind({**worker, "runId": "../opus-backend"})
    with pytest.raises(ValueError):
        sessions.bind({**worker, "sessionId": "22222222-2222-3333-4444-555555555555"})
    result = sessions.bind(worker)
    assert result["parentSessionId"] == HERMES_ID and result["role"] == "worker"
    assert result["model"] == "claude-test"


def test_claude_running_only_with_verified_pid_identity(service, lanes):
    write_lane(lanes, "opus-backend", running_state(), claude_events())
    worker = payload(source="claude", runId="opus-backend", sessionId=CLAUDE_ID, role="worker", title="Opus")
    matched = make(service, lanes, create_time=lambda pid: 1_700_000_000.5 if pid == 4242 else None)
    assert matched.bind(worker)["status"] == "running"
    mismatched = make(service, lanes, create_time=lambda pid: 1_700_009_999.0)
    session = mismatched.list("draft", "draft", "n1")["sessions"][0]
    assert session["status"] == "unknown" and "neběží" in session["statusReason"]
    dead = make(service, lanes, create_time=lambda pid: None)
    assert dead.list("draft", "draft", "n1")["sessions"][0]["status"] == "unknown"


@pytest.mark.parametrize(("overrides", "expected"), [
    ({"running": False, "finishedAt": observed(9), "success": True, "localTreeInactive": True}, "completed"),
    ({"running": False, "finishedAt": observed(9), "success": False, "localTreeInactive": True}, "failed"),
    ({"running": False, "finishedAt": None, "success": None}, "recent_activity"),
])
def test_claude_finish_states_and_safe_events(service, lanes, overrides, expected):
    write_lane(lanes, "opus-backend", running_state(**overrides), claude_events())
    sessions = make(service, lanes, clock=Clock(T0 + timedelta(seconds=20)))
    session = sessions.bind(payload(source="claude", runId="opus-backend", sessionId=CLAUDE_ID,
                                    role="worker", title="Opus"))
    assert session["status"] == expected
    assert [e["kind"] for e in session["events"]] == [
        "session_init", "tool_call", "tool_call", "tool_result", "tool_error", "result"]
    assert session["events"][1]["summary"] == "Volání nástroje: Bash"
    assert session["events"][2]["summary"] == "Volání nástroje (neuvedený nástroj)"
    assert len({e["id"] for e in session["events"]}) == 6
    assert session["metrics"] == {"inputTokens": 50, "outputTokens": 20, "costUsd": 0.07}
    assert session["lastActivityAt"] == observed(4)
    assert_safe(session)


def test_claude_skips_foreign_oversized_and_corrupt_lines(service, lanes):
    events = claude_events()
    events.insert(2, "{not json")
    events.insert(2, json.dumps({"type": "assistant", "session_id": CLAUDE_ID, "message": {"content": [
        {"type": "text", "text": "x" * 1_100_000}]}}))
    events.append({"type": "result", "is_error": True, "session_id": "other-session", "_observedAt": observed(5)})
    write_lane(lanes, "opus-backend", running_state(running=False), events)
    session = make(service, lanes).bind(payload(source="claude", runId="opus-backend", sessionId=CLAUDE_ID,
                                                 role="worker", title="Opus"))
    assert [e["kind"] for e in session["events"]][-1] == "result"
    assert len(session["events"]) == 6


def test_claude_events_are_bounded_to_last_fifty(service, lanes):
    events = claude_events()[:1] + [
        {"type": "assistant", "session_id": CLAUDE_ID, "_observedAt": observed(i),
         "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}]}} for i in range(120)]
    write_lane(lanes, "opus-backend", running_state(running=False), events)
    session = make(service, lanes).bind(payload(source="claude", runId="opus-backend", sessionId=CLAUDE_ID,
                                                 role="worker", title="Opus"))
    assert len(session["events"]) == 50 and session["lastActivityAt"] == observed(119)


@pytest.mark.skipif(sys.platform != "win32", reason="junction je Windows primitivum")
def test_claude_rejects_junction_lane(service, lanes, tmp_path):
    import _winapi

    outside = write_lane(tmp_path, "outside", running_state(), claude_events())
    _winapi.CreateJunction(str(outside), str(lanes / "linked"))
    source = ClaudeLaneSource(lanes)
    with pytest.raises(SourceError):
        source.verify("linked", CLAUDE_ID)


def test_lane_file_symlink_rejected(lanes, tmp_path):
    directory = write_lane(lanes, "opus-backend", None, [])
    outside = tmp_path / "state.json"
    outside.write_text(json.dumps(running_state()), encoding="utf-8")
    try:
        os.symlink(outside, directory / "state.json")
    except OSError:
        pytest.skip("symlink není v tomto prostředí povolený")
    with pytest.raises(SourceError):
        ClaudeLaneSource(lanes).verify("opus-backend", CLAUDE_ID)


def test_failing_source_keeps_rows_and_other_sources(service, lanes):
    fake = FakeHermes(service)
    write_lane(lanes, "opus-backend", running_state(running=False), claude_events())
    sessions = make(service, lanes, hermes_fetch=fake)
    sessions.bind(payload())
    sessions.bind(payload(source="claude", runId="opus-backend", sessionId=CLAUDE_ID, role="worker", title="Opus"))
    for failure in ("raise", 500, 401):
        fake.fail = failure
        listed = sessions.list("draft", "draft", "n1")["sessions"]
        by_source = {s["source"]: s for s in listed}
        assert by_source["hermes"]["sourceAvailable"] is False and by_source["hermes"]["status"] == "unknown"
        assert by_source["hermes"]["statusReason"].startswith("Zdroj nedostupný")
        assert by_source["claude"]["sourceAvailable"] is True
        assert_safe(listed)
    (lanes / "opus-backend" / "state.json").write_text("{corrupt", encoding="utf-8")
    fake.fail = None
    by_source = {s["source"]: s for s in sessions.list("draft", "draft")["sessions"]}
    assert by_source["claude"]["sourceAvailable"] is False and by_source["hermes"]["sourceAvailable"] is True


def test_list_scope_filter_and_truncation(service):
    class Unavailable:
        def observe(self, *args, **kwargs):
            assert not service.lock._is_owned()
            raise SourceError("test")

    sessions = NodeSessions(service, hermes=Unavailable(), claude=Unavailable(), clock=Clock())
    with service.lock, service.db:
        for index in range(101):
            service.db.execute(
                "INSERT INTO node_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL)",
                (f"r{index}", "draft", "draft", "n2" if index else "n1", "hermes", f"s{index}", None, "worker",
                 "T", None, observed(index), observed(index), 0),
            )
    everything = sessions.list("draft", "draft")
    assert len(everything["sessions"]) == 100 and everything["truncated"] is True
    assert everything["nodeId"] is None
    only = sessions.list("draft", "draft", "n1")
    assert [s["id"] for s in only["sessions"]] == ["r0"] and only["truncated"] is False
    with pytest.raises(ValueError):
        sessions.list("draft", "draft", "missing")


def test_hermes_transport_is_loopback_get_with_server_side_key(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    source = HermesSessionSource("http://127.0.0.1:8642/", "sk-live-SECRET-key")
    request = source.build_request("/api/sessions/x")
    assert request.get_method() == "GET" and request.full_url == "http://127.0.0.1:8642/api/sessions/x"
    assert request.get_header("Authorization") == "Bearer sk-live-SECRET-key"
    handlers = source._opener.handlers
    assert not any(getattr(h, "proxies", None) for h in handlers)
    assert any(type(h).__name__ == "_NoRedirectHandler" for h in handlers)
    for url in ("http://example.com:8642", "https://127.0.0.1:8642", "http://user:pw@127.0.0.1:8642"):
        with pytest.raises(SourceError, match="loopback"):
            HermesSessionSource(url, "k").session_meta(HERMES_ID)
    with pytest.raises(SourceError, match="klíč"):
        HermesSessionSource("http://127.0.0.1:8642", None).session_meta(HERMES_ID)


def test_router_contract_and_env_config(service, lanes, monkeypatch):
    monkeypatch.setenv("OPORA_HERMES_API_URL", "http://10.0.0.5:8642")
    monkeypatch.setenv("OPORA_HERMES_API_KEY", "sk-live-SECRET-key")
    monkeypatch.setenv("OPORA_NODE_SESSION_LANES_ROOT", str(lanes))
    write_lane(lanes, "opus-backend", running_state(running=False), claude_events())
    app = FastAPI()
    app.include_router(create_node_sessions_router(service, clock=Clock()))
    client = TestClient(app)
    rejected = client.post("/api/node-sessions/bind", json=payload())
    assert rejected.status_code == 409 and "SECRET" not in rejected.text
    created = client.post("/api/node-sessions/bind", json=payload(
        source="claude", runId="opus-backend", sessionId=CLAUDE_ID, role="worker", title="Opus"))
    assert created.status_code == 200
    body = client.get("/api/node-sessions", params={"project": "draft", "workspace": "draft", "nodeId": "n1"}).json()
    assert set(body) == {"project", "workspace", "nodeId", "sessions", "limit", "truncated"}
    assert set(body["sessions"][0]) == {
        "id", "source", "sessionId", "parentSessionId", "role", "title", "project", "workspace", "nodeId",
        "nodeName", "model", "status", "statusReason", "sourceAvailable", "lastActivityAt", "boundAt",
        "events", "metrics", "sourceLabel", "closedAt"}
    assert set(body["sessions"][0]["events"][0]) == {"id", "at", "kind", "summary"}
    assert client.get("/api/node-sessions", params={"project": "draft", "workspace": "draft",
                                                    "nodeId": "nope"}).status_code == 409


@pytest.mark.skipif(sys.platform != "win32", reason="ověření času vytvoření procesu je implementováno pro Windows")
def test_default_process_probe_reads_own_process_identity():
    created = default_process_create_time(os.getpid())
    assert created is not None and created <= time.time()
    assert default_process_create_time(0) is None and default_process_create_time(True) is None


def test_close_freezes_attribution_and_allows_next_node(service):
    fake = FakeHermes(service)
    sessions = make(service, hermes_fetch=fake)
    row = sessions.bind(payload())
    scope = {"project": "draft", "workspace": "draft", "nodeId": "n1", "confirmed": True}
    closed = sessions.close(row["id"], scope)
    assert closed["closedAt"] is not None and closed["status"] == "idle"
    calls = len(fake.calls)
    fake.session["message_count"] = 50
    frozen = sessions.list("draft", "draft", "n1")["sessions"][0]
    assert frozen == closed
    assert len(fake.calls) == calls  # pozdější práce se k uzlu nesmí připisovat
    assert sessions.close(row["id"], scope) == closed
    next_row = sessions.bind(payload(nodeId="n2"))
    assert next_row["id"] != row["id"] and next_row["closedAt"] is None
    assert_safe(frozen)


def test_close_rejects_wrong_scope_and_missing_confirmation(service):
    sessions = make(service)
    row = sessions.bind(payload())
    for scope in (
        {"project": "draft", "workspace": "draft", "nodeId": "n2", "confirmed": True},
        {"project": "draft", "workspace": "draft", "nodeId": "n1", "confirmed": False},
    ):
        with pytest.raises(ValueError):
            sessions.close(row["id"], scope)
    assert sessions.list("draft", "draft", "n1")["sessions"][0]["closedAt"] is None
