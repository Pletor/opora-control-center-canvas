"""Claude Code: bezpečná pole ze settings.json, tajné soubory se neotevřou, verze přes falešný proces."""
import json
import subprocess

import pytest

from backend.pletor.llm_settings import claude
from backend.pletor.llm_settings.conftest import fake_run

SETTINGS = {
    "model": "opus",
    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "a"},
                                                            {"type": "command", "command": "b"}]}],
              "Stop": [{"hooks": [{"type": "command", "command": "c"}]}]},
    "mcpServers": {"zeta": {"command": "z", "env": {"TOKEN": "SECRET-ENV"}}, "alfa": {"command": "a"}},
    "permissions": {"defaultMode": "acceptEdits", "allow": ["Bash(ls)"]},
    "env": {"ANTHROPIC_API_KEY": "SECRET-KEY"},
}


def seed(home):
    root = home / ".claude"
    (root / "skills" / "one").mkdir(parents=True)
    (root / "skills" / "two").mkdir()
    (root / "skills" / "note.txt").write_text("x", encoding="utf-8")
    (root / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
    (root / "CLAUDE.md").write_text("# pravidla", encoding="utf-8")
    (root / ".credentials.json").write_text('{"token": "SECRET-TOKEN"}', encoding="utf-8")
    (home / ".claude.json").write_text('{"oauthAccount": "SECRET-ACCOUNT"}', encoding="utf-8")


def test_reads_only_safe_fields(home):
    seed(home)
    out = claude.read(find=lambda: "claude", run=fake_run({"--version": "2.1.0 (Claude Code)\n"}))
    assert out == {"available": True, "reason": None, "version": "2.1.0 (Claude Code)", "model": "opus", "hooks": 3,
                   "mcp": ["alfa", "zeta"], "permissionsMode": "acceptEdits", "loggedIn": True, "claudeMd": True,
                   "skills": 2}
    assert "SECRET" not in json.dumps(out)


def test_guard_refuses_secret_files(home):
    seed(home)
    with pytest.raises(AssertionError):
        (home / ".claude" / ".credentials.json").read_text(encoding="utf-8")


def test_missing_install_and_failing_cli(home):
    out = claude.read(find=lambda: None)
    assert out["available"] is False and out["reason"] and out["version"] is None and out["loggedIn"] is False
    (home / ".claude").mkdir()
    slow = claude.read(find=lambda: "claude", run=fake_run({"--version": subprocess.TimeoutExpired("claude", 5)}))
    assert slow["available"] is True and slow["version"] is None and slow["mcp"] == [] and slow["hooks"] == 0
