"""Claude Code na tomto počítači: bezpečná pole z `~/.claude/settings.json`, verze CLI, CLAUDE.md a počet skills.

`.credentials.json` ani `~/.claude.json` (tokeny) se nikdy neotevírají; přihlášení = jen existence souboru.
"""
import json
import subprocess
from pathlib import Path

from backend.brain_opora.heart.command import find_claude
from backend.agi_pletor.llm_settings import cli


def _hooks(hooks):
    """Počet příkazů háčků: `{událost: [{matcher, hooks: [...]}, ...]}`."""
    if not isinstance(hooks, dict):
        return 0
    groups = [group for value in hooks.values() if isinstance(value, list) for group in value]
    return sum(len(group.get("hooks") or []) if isinstance(group, dict) else 0 for group in groups)


def read(find=find_claude, run=subprocess.run):
    root = Path.home() / ".claude"
    path = root / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(settings, dict):
        settings = {}
    mcp = settings.get("mcpServers")
    permissions = settings.get("permissions")
    skills = root / "skills"
    binary = find()
    available = bool(binary) or root.is_dir()
    return {
        "available": available,
        "reason": None if available else "Claude Code není nainstalovaný (chybí CLI i složka v domově).",
        "version": cli.version(binary, run),
        "model": settings.get("model") if isinstance(settings.get("model"), str) else None,
        "hooks": _hooks(settings.get("hooks")),
        "mcp": sorted(mcp) if isinstance(mcp, dict) else [],
        "permissionsMode": permissions.get("defaultMode") if isinstance(permissions, dict) else None,
        "loggedIn": (root / ".credentials.json").exists(),
        "claudeMd": (root / "CLAUDE.md").is_file(),
        "skills": sum(1 for item in skills.iterdir() if item.is_dir()) if skills.is_dir() else 0,
    }
