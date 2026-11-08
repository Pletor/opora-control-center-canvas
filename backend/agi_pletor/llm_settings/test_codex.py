"""Codex: pole z config.toml, auth.json se neotevře, chybějící CLI."""
import json

from backend.agi_pletor.llm_settings import codex
from backend.agi_pletor.llm_settings.conftest import Done, fake_run

CONFIG = """model = "gpt-5.5-codex"
model_reasoning_effort = "high"
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[mcp_servers.context7]
command = "npx"
env = { API_KEY = "SECRET-ENV" }

[mcp_servers.playwright]
command = "npx"
"""


def test_reads_config_without_auth(home):
    root = home / ".codex"
    root.mkdir()
    (root / "config.toml").write_text(CONFIG, encoding="utf-8")
    (root / "auth.json").write_text('{"tokens": "SECRET-TOKEN"}', encoding="utf-8")
    out = codex.read(which=lambda name: "codex", run=fake_run({"--version": "codex-cli 0.80.0\n"}))
    assert out == {"available": True, "reason": None, "version": "codex-cli 0.80.0", "model": "gpt-5.5-codex",
                   "models": [], "reasoning": "high", "approval": "on-request", "sandbox": "workspace-write",
                   "mcp": ["context7", "playwright"], "loggedIn": True}
    assert "SECRET" not in json.dumps(out)


def test_not_installed_and_cli_error(home):
    assert codex.read(which=lambda name: None)["available"] is False
    (home / ".codex").mkdir()
    out = codex.read(which=lambda name: "codex", run=fake_run({"--version": Done("", 1)}))
    assert out["available"] is True and out["version"] is None and out["loggedIn"] is False and out["model"] is None


def test_models_from_cache_list_only_and_no_identity(home):
    root = home / ".codex"
    root.mkdir()
    cache = {"identity": "SECRET-IDENTITY", "models": [
        {"slug": "gpt-a", "display_name": "GPT A", "visibility": "list",
         "supported_reasoning_levels": [{"effort": "low", "description": "x"}, {"effort": "high", "description": "y"}]},
        {"slug": "skryty", "display_name": "Skrytý", "visibility": "hide", "supported_reasoning_levels": []}]}
    (root / "models_cache.json").write_text(json.dumps(cache), encoding="utf-8")
    out = codex.models()
    assert out == [{"id": "gpt-a", "label": "GPT A", "reasoning": ["low", "high"]}]
    assert "SECRET" not in json.dumps(out)


def test_models_missing_or_broken_cache_is_empty(home):
    assert codex.models() == []
    (home / ".codex").mkdir()
    (home / ".codex" / "models_cache.json").write_text('{"models": 5', encoding="utf-8")
    assert codex.models() == []
