"""Codex na tomto počítači: bezpečná pole z `~/.codex/config.toml` a verze CLI.

`auth.json` (tokeny) se nikdy neotevírá; přihlášení = jen existence souboru.
"""
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

from backend.agi_pletor.llm_settings import cli


def _text(value):
    return value if isinstance(value, str) else None


def models():
    """Modely aktivního účtu z `~/.codex/models_cache.json` (jen viditelné, jen id/label/reasoning); chyba = `[]`."""
    try:
        listed = json.loads((Path.home() / ".codex" / "models_cache.json").read_text(encoding="utf-8"))["models"]
        return [{"id": item["slug"], "label": item.get("display_name") or item["slug"],
                 "reasoning": [level["effort"] for level in item.get("supported_reasoning_levels") or []]}
                for item in listed if item.get("visibility") == "list"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


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
        "models": models(),
        "reasoning": _text(config.get("model_reasoning_effort")),
        "approval": _text(config.get("approval_policy")),
        "sandbox": _text(config.get("sandbox_mode")),
        "mcp": sorted(mcp) if isinstance(mcp, dict) else [],
        "loggedIn": (root / "auth.json").exists(),
    }
