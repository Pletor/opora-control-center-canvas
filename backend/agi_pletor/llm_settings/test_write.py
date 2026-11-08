"""Zápis modelu: záloha, zachování ostatních klíčů, validace, tajné soubory zůstanou nedotčené."""
import json
import tomllib

import pytest

from backend.agi_pletor.llm_settings import write


def test_claude_keeps_keys_and_backs_up(home):
    path = home / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"model": "opus", "env": {"A": "1"}}), encoding="utf-8")
    out = write.claude_model("sonnet")
    assert out["model"] == "sonnet" and out["backup"].startswith("settings.json.bak-")
    assert json.loads(path.read_text(encoding="utf-8")) == {"model": "sonnet", "env": {"A": "1"}}
    assert json.loads((path.parent / out["backup"]).read_text(encoding="utf-8"))["model"] == "opus"


def test_claude_creates_missing_file_without_backup(home):
    assert write.claude_model("opus")["backup"] is None
    assert json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8")) == {"model": "opus"}


def test_codex_replaces_and_inserts_top_level_only(home):
    path = home / ".codex" / "config.toml"
    path.parent.mkdir()
    path.write_text('model = "gpt-5"\napproval_policy = "never"\n\n[mcp_servers.x]\nmodel = "inner"\ncommand = "c"\n', encoding="utf-8")
    out = write.codex_model("gpt-6", "high")
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    assert config["model"] == "gpt-6" and config["model_reasoning_effort"] == "high" and config["approval_policy"] == "never"
    assert config["mcp_servers"]["x"] == {"model": "inner", "command": "c"}
    assert out["backup"].startswith("config.toml.bak-") and out["model"] == "gpt-6"


@pytest.mark.parametrize("model", ["", " ", "a b", "x" * 101, 'a"b', "a\nb", None, 3])
def test_rejects_bad_model(home, model):
    with pytest.raises(ValueError):
        write.claude_model(model)
    with pytest.raises(ValueError):
        write.codex_model(model)
    assert not (home / ".claude").exists() and not (home / ".codex").exists()


def test_rejects_bad_reasoning(home):
    with pytest.raises(ValueError):
        write.codex_model("gpt-6", "extreme")


def test_claude_effort_written_and_removed_with_backup(home):
    path = home / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"model": "opus", "env": {"A": "1"}}), encoding="utf-8")
    out = write.claude_model("opus", "xhigh")
    assert json.loads(path.read_text(encoding="utf-8")) == {"model": "opus", "env": {"A": "1"}, "effortLevel": "xhigh"}
    assert out["backup"].startswith("settings.json.bak-")
    write.claude_model("opus")  # výchozí = effortLevel pryč
    assert "effortLevel" not in json.loads(path.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        write.claude_model("opus", "extreme")


def test_codex_reasoning_follows_cache_and_default_removes_key(home, monkeypatch):
    path = home / ".codex" / "config.toml"
    path.parent.mkdir()
    path.write_text('model = "gpt-5"\nmodel_reasoning_effort = "high"\n[mcp_servers.x]\ncommand = "c"\n', encoding="utf-8")
    monkeypatch.setattr(write.codex, "models", lambda: [{"id": "gpt-6", "label": "6", "reasoning": ["low", "xhigh"]}])
    write.codex_model("gpt-6", "xhigh")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["model_reasoning_effort"] == "xhigh"
    with pytest.raises(ValueError):
        write.codex_model("gpt-6", "medium")  # cache tento model nezná
    write.codex_model("gpt-6")
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    assert "model_reasoning_effort" not in config and config["mcp_servers"]["x"] == {"command": "c"}
