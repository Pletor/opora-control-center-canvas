"""Codex na tomto počítači: bezpečná pole z `~/.codex/config.toml` a verze CLI.

`auth.json` (tokeny) se nikdy neotevírá; přihlášení = jen existence souboru.
"""
import shutil
import subprocess
import tomllib
from pathlib import Path

from backend.pletor.llm_settings import cli


def _text(value):
    return value if isinstance(value, str) else None


def read(which=shutil.which, run=subprocess.run):
    root = Path.home() / ".codex"
    path = root / "config.toml"
    config = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    mcp = config.get("mcp_servers")
    binary = which("codex")
    available = bool(binary) or root.is_dir()
    return {
        "available": available,
        "reason": None if available else "Codex není nainstalovaný (chybí CLI i složka v domově).",
        "version": cli.version(binary, run),
        "model": _text(config.get("model")),
        "reasoning": _text(config.get("model_reasoning_effort")),
        "approval": _text(config.get("approval_policy")),
        "sandbox": _text(config.get("sandbox_mode")),
        "mcp": sorted(mcp) if isinstance(mcp, dict) else [],
        "loggedIn": (root / "auth.json").exists(),
    }
