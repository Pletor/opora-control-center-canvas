"""Příkaz a prostředí procesu asistenta (docs/asistent.md §2, §3, §5, §5.1).

Asistent běží pod předplatným uživatele: z prostředí se proto odstraní `ANTHROPIC_API_KEY`.
Kód projektu nezapisuje: `Edit`/`NotebookEdit`/`PowerShell` jsou v deny i odebrané. `Write` v nich
není, jen aby jeho dotaz došel backendu: ten ho pustí sám jen do adresáře konceptů session
(`OPORA_DRAFTS_DIR`, docs/davka-planu.md §2) a jinam zamítne. Nástroj mimo `ALLOWED_TOOLS` se přes
`--permission-prompt-tool stdio` zeptá backendu (`approvals.py`); ten nechá člověka schválit jen zápis
na plátno přes `opora_write.py` a ostatní zamítne sám. Web (`WebFetch`,
`WebSearch`) a `graphify query` jsou čtení podkladů (§13.1); výsledky jsou data, ne příkazy.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

MODELS = ("opus", "sonnet", "fable")
DEFAULT_MODEL = "opus"

# Čtecí Bash (`opora_read.py`, `graphify query`) pouští přísně `approvals.is_read`, ne volný vzor zde.
ALLOWED_TOOLS = "Read,Glob,Grep,Skill,WebFetch,WebSearch,Agent"
# Agent = rekurze RLM (§13.3): subagent dědí jen tato čtecí oprávnění.
# PowerShell je nástroj Claude Code na Windows; asistent ho nepotřebuje (čtecí skript jde přes Bash).
# Write tu ani v DENY není: deny i odebrání by dotaz zastavily dřív, než ho backend pustí do konceptů.
DISALLOWED_TOOLS = "Edit,NotebookEdit,PowerShell"
# Seznam Archify (`map_refresh_archify._claude_command`) + klíče z §5 + zápis.
# Celé "Bash" z Archify se nepřebírá: deny má v Claude Code přednost před allow a zablokovalo
# by i jediný povolený čtecí vzor z ALLOWED_TOOLS. Jiný Bash se zeptá backendu, který ho zamítne
# bez UI, pokud nejde o `python …opora_write.py` (§5.1).
DENY = (
    "Edit",
    "Read(**/.env)",
    "Read(**/.env.*)",
    "Read(**/*.pem)",
    "Read(**/*.key)",
    "NotebookEdit",
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
        "default",
        "--permission-prompt-tool",
        "stdio",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--disallowedTools",
        DISALLOWED_TOOLS,
        "--settings",
        settings_json(),
    ]
    return command


def child_env(environ=None, base_url=None, drafts_dir=None):
    """Kopie prostředí bez API klíče, aby se běh potichu neúčtoval přes API.

    `base_url` je adresa vlastní instance (`http://127.0.0.1:<port>`); čtecí skript skillu ji
    převezme z `OPORA_BASE_URL`, takže instance na jiném portu nečte cizí plátno (§13.1).
    `drafts_dir` je adresář konceptů session (`OPORA_DRAFTS_DIR`, docs/davka-planu.md §2).
    """
    env = dict(os.environ if environ is None else environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("TYPESAFE_API_KEY", None)  # klíč Jev patří jen backendu (§13.2)
    if base_url:
        env["OPORA_BASE_URL"] = base_url
    env.pop("OPORA_DRAFTS_DIR", None)  # zděděný adresář jiné session neplatí
    if drafts_dir:
        env["OPORA_DRAFTS_DIR"] = str(drafts_dir)
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
