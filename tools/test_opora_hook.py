"""Hook client: stdout je vždy jeden JSON objekt; režim memory se ptá serveru na roli."""

import json

import pytest

from tools import opora_hook

CONFIG = {
    "endpoint": "http://127.0.0.1:8740/api/agent-hooks", "bindingId": "b1",
    "sessionId": "50e5d2f5-d3aa-4eed-8eed-f413766b88b8", "project": "draft",
    "workspace": "draft", "nodeId": "focus", "token": "t",
}


def write_config(tmp_path, **overrides):
    path = tmp_path / "client.json"
    path.write_text(json.dumps({**CONFIG, **overrides}), encoding="utf-8")
    return path


def test_client_config_must_carry_the_card(tmp_path):
    without = dict(CONFIG)
    del without["nodeId"]
    path = tmp_path / "old.json"
    path.write_text(json.dumps(without), encoding="utf-8")
    with pytest.raises(ValueError):
        opora_hook.load_client(path)
    assert opora_hook.load_client(write_config(tmp_path))["nodeId"] == "focus"


def test_memory_mode_posts_the_card_scope_and_lets_the_server_pick_the_role(tmp_path, monkeypatch):
    sent = {}

    def fake_request(client, path, payload):
        sent["path"], sent["payload"] = path, payload
        return {"status": "configured", "role": "role-backend", "items": []}

    monkeypatch.setattr(opora_hook, "request", fake_request)
    code = opora_hook.main(["--client", str(write_config(tmp_path)), "memory", "kam patří router"])
    assert code == 0
    assert sent["path"] == "/api/memory/recall"
    assert sent["payload"] == {"role": None, "project": "draft", "workspace": "draft",
                               "nodeId": "focus", "query": "kam patří router", "maxTokens": 600}


def test_memory_mode_refuses_an_empty_or_oversized_query(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(opora_hook, "request", lambda *args: {"ok": True})
    for query in ("   ", "x" * 2001):
        opora_hook.main(["--client", str(write_config(tmp_path)), "memory", query])
        assert json.loads(capsys.readouterr().out)["continue"] is False


def test_memory_mode_needs_exactly_one_argument(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(opora_hook, "request", lambda *args: {"ok": True})
    opora_hook.main(["--client", str(write_config(tmp_path)), "memory", "a", "b"])
    assert json.loads(capsys.readouterr().out)["continue"] is False
