import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent_installation.vscode_installer import VscodeHookInstaller
from backend.api.live_run.hook_install_routes import create_hook_install_router

SESSION = "123e4567-e89b-42d3-a456-426614174000"
BINDING_ID = "binding-001"


def setup_installer(tmp_path, *, state="active", read_only=False):
    root = tmp_path / "workspace"
    root.mkdir(parents=True)
    private = tmp_path / "app" / "agent-control" / "settings"
    private.mkdir(parents=True)
    source = private / "binding.json"
    command = 'python -I "C:/app/tools/opora_hook.py" --client "C:/private/client.json"'
    source.write_text(json.dumps({"hooks": {name: [{"matcher": ".*", "hooks": [{"type": "command", "command": command}]}]
                                           for name in ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop")}}), encoding="utf-8")
    binding = {"id": BINDING_ID, "project": "p", "workspace": "draft", "nodeId": "n", "sessionId": SESSION,
               "revision": 7, "state": state, "settingsPath": str(source), "launchCommand": command}
    service = SimpleNamespace(root=tmp_path / "app", workspace_sources=SimpleNamespace(root=lambda project, workspace: root),
                              view=lambda project, workspace: {"readOnly": read_only})
    return VscodeHookInstaller(service, lambda binding_id: binding if binding_id == BINDING_ID else None), root, binding, command


def test_install_is_idempotent_and_remove_preserves_foreign_settings(tmp_path):
    installer, root, binding, command = setup_installer(tmp_path)
    target = root / ".claude" / "settings.local.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"custom": {"keep": True}, "hooks": {"Stop": [{"matcher": "foreign", "hooks": [{"type": "command", "command": "keep"}]}]}}), encoding="utf-8")
    before = hashlib.sha256(target.read_bytes()).hexdigest()

    state = installer.apply(BINDING_ID, 7, before, "install", True)
    installed = json.loads(target.read_text(encoding="utf-8"))
    own = command + " --only-session " + SESSION
    assert state["installed"] is True and state["backupCreated"] is True
    assert installed["custom"] == {"keep": True}
    assert sum(item["command"] == own for event in installed["hooks"].values() for rule in event for item in rule["hooks"]) == 5

    repeat = installer.apply(BINDING_ID, 7, state["settingsDigest"], "install", True)
    assert repeat["backupCreated"] is False
    assert sum(item["command"] == own for event in json.loads(target.read_text())["hooks"].values() for rule in event for item in rule["hooks"]) == 5

    removed = installer.apply(BINDING_ID, 7, repeat["settingsDigest"], "remove", True)
    restored = json.loads(target.read_text(encoding="utf-8"))
    assert removed["installed"] is False and restored["custom"] == {"keep": True}
    assert restored["hooks"]["Stop"][0]["hooks"][0]["command"] == "keep"


def test_refuses_stale_readonly_path_escape_corrupt_source_and_config_without_writes(tmp_path):
    installer, root, binding, command = setup_installer(tmp_path)
    target = root / ".claude" / "settings.local.json"
    target.parent.mkdir()
    target.write_text('{"keep": true}', encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        installer.apply(BINDING_ID, 6, digest, "install", True)
    with pytest.raises(ValueError):
        installer.apply(BINDING_ID, 7, "0" * 64, "install", True)
    assert target.read_text(encoding="utf-8") == '{"keep": true}'

    target.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        installer.apply(BINDING_ID, 7, hashlib.sha256(target.read_bytes()).hexdigest(), "install", True)
    assert target.read_text(encoding="utf-8") == "{broken"

    escaped = tmp_path / "outside.json"
    escaped.write_text('{"hooks": {}}', encoding="utf-8")
    target.write_text('{"keep": true}', encoding="utf-8")
    binding["settingsPath"] = str(escaped)
    with pytest.raises(ValueError):
        installer.status(BINDING_ID)
    assert target.read_text(encoding="utf-8") == '{"keep": true}'

    installer, root, binding, command = setup_installer(tmp_path / "readonly", read_only=True)
    with pytest.raises(ValueError):
        installer.apply(BINDING_ID, 7, None, "install", True)


def test_vscode_routes_require_exact_dtos_and_never_return_config(tmp_path):
    installer, root, binding, command = setup_installer(tmp_path)
    app = FastAPI()
    app.include_router(create_hook_install_router(installer.service, binding_lookup=lambda binding_id: binding if binding_id == BINDING_ID else None))
    client = TestClient(app)
    missing = client.get("/api/agent-hooks/vscode", params={"bindingId": BINDING_ID})
    assert missing.status_code == 200 and set(missing.json()) == {"bindingId", "sessionId", "project", "workspace", "nodeId", "installed", "settingsPath", "settingsDigest", "canInstall", "detail"}
    rejected = client.post("/api/agent-hooks/vscode", json={"bindingId": BINDING_ID})
    assert rejected.status_code == 409
    payload = {"bindingId": BINDING_ID, "expectedBindingRevision": 7, "expectedSettingsDigest": None, "action": "install", "confirmed": True}
    installed = client.post("/api/agent-hooks/vscode", json=payload)
    assert installed.status_code == 200 and "hooks" not in installed.text and "client.json" not in installed.text
