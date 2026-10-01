import json
import threading
from pathlib import Path

import pytest

from backend.agent_control.hook_control import HookControl


class FakeSources:
    def __init__(self, root):
        self.root_path = root

    def root(self, project, workspace):
        return self.root_path


class FakeService:
    def __init__(self, root):
        self.root = root / "data"
        self.root.mkdir()
        self.lock = threading.RLock()
        self.workspace_sources = FakeSources(root / "worktree")
        self.workspace_sources.root_path.mkdir()
        self.task_revision = 3
        self.closed = False

    def view(self, project, workspace):
        return {"readOnly": False, "graph": {"nodes": [{"id": "node"}]}}

    def node_spec(self, project, workspace, node_id):
        return {"revision": self.task_revision}


def payload(session="50e5d2f5-d3aa-4eed-8eed-f413766b88b8", paths=None):
    return {
        "project": "draft", "workspace": "draft", "nodeId": "node", "sessionId": session,
        "allowedPaths": paths or ["backend"], "maxToolCalls": 4, "maxFailures": 2,
        "ttlSeconds": 600, "allowTextSearch": False, "confirmed": True,
    }


def event(name="Write", path="backend/new.py", session="50e5d2f5-d3aa-4eed-8eed-f413766b88b8", cwd=""):
    return {"hook_event_name": "PreToolUse", "session_id": session, "cwd": cwd, "tool_name": name,
            "tool_input": {"file_path": path}}


def client_token(control, binding_id):
    row = control._binding(binding_id)
    return json.loads(Path(row["client_path"]).read_text(encoding="utf-8"))["token"]


def test_binding_is_private_and_only_scoped_events_are_allowed(tmp_path):
    service = FakeService(tmp_path)
    control = HookControl(service, port=8740)
    created = control.bind(payload())
    binding = created["binding"]
    assert binding["identityVerified"] is False
    assert "token" not in json.dumps(created)
    assert Path(created["settingsPath"]).is_file()

    denied = control.event(binding["id"], client_token(control, binding["id"]), event(path="outside.py", cwd=str(service.workspace_sources.root_path)))
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"

    permitted = control.event(binding["id"], client_token(control, binding["id"]), event(cwd=str(service.workspace_sources.root_path)))
    assert permitted == {}
    assert control.list("draft", "draft", "node")["bindings"][0]["hookObserved"] is True


def test_new_revision_requires_exact_ack_and_stopped_binding_halts_next_event(tmp_path):
    service = FakeService(tmp_path)
    control = HookControl(service, port=8740)
    binding = control.bind(payload())["binding"]
    token = client_token(control, binding["id"])
    service.task_revision = 4
    blocked = control.event(binding["id"], token, event(cwd=str(service.workspace_sources.root_path)))
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "ack" in blocked["hookSpecificOutput"]["permissionDecisionReason"]
    with pytest.raises(ValueError):
        control.ack(binding["id"], token, binding["sessionId"], 3)
    assert control.ack(binding["id"], token, binding["sessionId"], 4)["acknowledgedRevision"] == 4
    assert control.event(binding["id"], token, event(cwd=str(service.workspace_sources.root_path))) == {}
    current = control.list("draft", "draft", "node")["bindings"][0]
    stopped = control.control(binding["id"], current["revision"], "stop")
    halted = control.event(binding["id"], token, event(cwd=str(service.workspace_sources.root_path)))
    assert stopped["state"] == "stopped"
    assert halted["continue"] is False


def test_duplicate_overlapping_paths_and_bash_are_denied(tmp_path):
    service = FakeService(tmp_path)
    control = HookControl(service, port=8740)
    control.bind(payload(paths=["backend"]))
    with pytest.raises(ValueError, match="překrývají"):
        control.bind(payload(session="68e5d2f5-d3aa-4eed-8eed-f413766b88b8", paths=["backend/api"]))
    binding = control.bind(payload(session="78e5d2f5-d3aa-4eed-8eed-f413766b88b8", paths=["tools"]))["binding"]
    bash = event(name="Bash", path="tools/x.py", session=binding["sessionId"], cwd=str(service.workspace_sources.root_path))
    bash["tool_input"] = {"command": "echo unsafe"}
    denied = control.event(binding["id"], client_token(control, binding["id"]), bash)
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    trusted = event(name="Bash", session=binding["sessionId"], cwd=str(service.workspace_sources.root_path))
    private = control._binding(binding["id"])["data"]
    trusted["tool_input"] = {"command": f'{private["clientCommand"]} code-query python definition tools/x.py 0 0'}
    assert control.event(binding["id"], client_token(control, binding["id"]), trusted) == {}


# ---- paměť role v Hooku ------------------------------------------------------------


class FakeStateStore:
    def __init__(self, role=None):
        self.role = role

    def current(self, project, workspace):
        return {"revision": 1, "state": {"nodes": {"node": {"agentRole": self.role}}}}


class FakeMemory:
    def __init__(self, status="configured", rendered="Router patří do api."):
        self.state = status
        self.rendered = rendered
        self.calls = []

    def status(self):
        self.calls.append("status")
        return {"status": self.state, "reason": "", "url": "http://127.0.0.1:1933"}

    def recall(self, role, project, node_id, query, max_tokens=600):
        self.calls.append(("recall", role, project, node_id, max_tokens))
        if self.state != "configured":
            return {"status": self.state, "role": role, "items": [], "rendered": "", "truncated": False}
        return {"status": "configured", "role": role, "rendered": self.rendered,
                "items": [{"uri": "viking://user/role-backend/memories/a.md", "text": self.rendered,
                           "score": 0.9, "origin": "self"}], "truncated": False}


def session_start(session="50e5d2f5-d3aa-4eed-8eed-f413766b88b8", cwd=""):
    return {"hook_event_name": "SessionStart", "session_id": session, "cwd": cwd,
            "tool_name": "", "tool_input": {}}


def bound(tmp_path, role=None, memory=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    service = FakeService(tmp_path)
    service.desktop_v3_state = FakeStateStore(role)
    if memory is not None:
        service.memory_service = memory
    control = HookControl(service, port=8740)
    binding = control.bind(payload())["binding"]
    return service, control, binding


def test_session_start_carries_the_role_memory_and_the_exact_memory_command(tmp_path):
    memory = FakeMemory()
    service, control, binding = bound(tmp_path, role="role-backend", memory=memory)
    started = control.event(binding["id"], client_token(control, binding["id"]),
                            session_start(cwd=str(service.workspace_sources.root_path)))
    context = started["hookSpecificOutput"]["additionalContext"]
    assert "Paměť role role-backend" in context and "Router patří do api." in context
    assert 'memory "<dotaz>"' in context
    assert ("recall", "role-backend", "draft", "node", 350) in memory.calls


def test_a_card_without_a_role_or_a_memory_that_is_not_configured_adds_nothing(tmp_path):
    service, control, binding = bound(tmp_path, role=None, memory=FakeMemory())
    started = control.event(binding["id"], client_token(control, binding["id"]),
                            session_start(cwd=str(service.workspace_sources.root_path)))
    assert "Paměť role" not in started["hookSpecificOutput"]["additionalContext"]

    down = FakeMemory(status="unavailable")
    service, control, binding = bound(tmp_path / "b", role="role-backend", memory=down)
    started = control.event(binding["id"], client_token(control, binding["id"]),
                            session_start(cwd=str(service.workspace_sources.root_path)))
    assert "Paměť role" not in started["hookSpecificOutput"]["additionalContext"]

    service, control, binding = bound(tmp_path / "c", role="role-backend")
    started = control.event(binding["id"], client_token(control, binding["id"]),
                            session_start(cwd=str(service.workspace_sources.root_path)))
    assert "Paměť role" not in started["hookSpecificOutput"]["additionalContext"]


def test_the_memory_block_stays_bounded(tmp_path):
    memory = FakeMemory(rendered="x" * 9000)
    service, control, binding = bound(tmp_path, role="role-backend", memory=memory)
    context = control.event(binding["id"], client_token(control, binding["id"]),
                            session_start(cwd=str(service.workspace_sources.root_path))
                            )["hookSpecificOutput"]["additionalContext"]
    assert "x" * 1501 not in context and "x" * 1500 in context


def test_bash_accepts_exactly_one_bounded_memory_argument(tmp_path):
    service, control, binding = bound(tmp_path, role="role-backend", memory=FakeMemory())
    private = control._binding(binding["id"])["data"]
    prefix = private["clientCommand"]
    assert control._trusted_bash(private, f'{prefix} memory "kam patří router"') == ("memory", None)
    assert control._trusted_bash(private, f'{prefix} memory "a" "b"') is None
    assert control._trusted_bash(private, f"{prefix} memory") is None
    assert control._trusted_bash(private, f'{prefix} memory ""') is None
    assert control._trusted_bash(private, f'{prefix} memory "{"x" * 2001}"') is None
    assert control._trusted_bash(private, f'{prefix} memory "a" && rm -rf /') is None

    allowed = event(name="Bash", session=binding["sessionId"], cwd=str(service.workspace_sources.root_path))
    allowed["tool_input"] = {"command": f'{prefix} memory "kam patří router"'}
    assert control.event(binding["id"], client_token(control, binding["id"]), allowed) == {}


def test_the_private_client_config_carries_the_card_but_never_the_role(tmp_path):
    _service, control, binding = bound(tmp_path, role="role-backend", memory=FakeMemory())
    config = json.loads(Path(control._binding(binding["id"])["client_path"]).read_text(encoding="utf-8"))
    assert config["nodeId"] == "node"
    assert "role" not in config and "agentRole" not in config
