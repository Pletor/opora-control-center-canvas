"""Příkaz a prostředí procesu asistenta (docs/asistent.md §2, §3, §5 fáze 1).

Asistent běží pod předplatným uživatele: z prostředí se proto odstraní `ANTHROPIC_API_KEY`.
Fáze 1 jen čte a radí; zápis je zakázaný seznamem deny i odebranými nástroji.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

MODELS = ("opus", "sonnet", "fable")
DEFAULT_MODEL = "opus"

ALLOWED_TOOLS = "Read,Glob,Grep,Skill,Bash(python *opora_read.py*)"
# PowerShell je nástroj Claude Code na Windows; asistent ho nepotřebuje (čtecí skript jde přes Bash).
DISALLOWED_TOOLS = "Edit,Write,NotebookEdit,WebFetch,WebSearch,PowerShell"
# Seznam Archify (`map_refresh_archify._claude_command`) + klíče z §5 + zápis a síť.
# Celé "Bash" z Archify se nepřebírá: deny má v Claude Code přednost před allow a zablokovalo
# by i jediný povolený čtecí vzor z ALLOWED_TOOLS. Jiný Bash zamítne `--permission-mode dontAsk`.
DENY = (
    "Write",
    "Edit",
    "Read(**/.env)",
    "Read(**/.env.*)",
    "Read(**/*.pem)",
    "Read(**/*.key)",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "PowerShell",
)


def find_claude(which=shutil.which):
    return which("claude")


def settings_json():
    settings = {"disableAllHooks": True, "permissions": {"deny": list(DENY)}}
    return json.dumps(settings, separators=(",", ":"))


def build_command(claude, model=DEFAULT_MODEL, resume=None):
    if model not in MODELS:
        raise ValueError("Neznámý model asistenta.")
    command = [
        claude,
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--model",
        model,
    ]
    if resume:
        command += ["--resume", resume]
    command += [
        "--setting-sources",
        "user,project",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--disallowedTools",
        DISALLOWED_TOOLS,
        "--settings",
        settings_json(),
    ]
    return command


def child_env(environ=None):
    """Kopie prostředí bez API klíče, aby se běh potichu neúčtoval přes API."""
    env = dict(os.environ if environ is None else environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def claude_version(claude, *, timeout=10, run=subprocess.run):
    """`claude --version` bez spuštění modelu; None, když odpověď nepřijde do limitu."""
    options = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace",
               "timeout": timeout, "shell": False, "env": child_env(), "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        options["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        completed = run([claude, "--version"], **options)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (completed.stdout or "").strip().splitlines()
    return lines[0][:120] if completed.returncode == 0 and lines else None
