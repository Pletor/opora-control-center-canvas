"""Příkazová řádka a prostředí jedné dávky srdce (docs/brain-heart.md §2).

Srdce běží jako jednorázový `claude -p` pod předplatným: Haiku jako hlavní model, Opus jako poradce.
Z prostředí se odstraní klíče API (běh se nesmí potichu účtovat přes API). Srdce smí jen číst a volat svůj
nástroj `opora_heart.py`; `dontAsk` odmítne každý nástroj mimo `allowedTools`, takže Edit/Write neprojdou nikde.
Deny pravidla v nastavení jsou druhá pojistka nad zdrojem projektu (`--add-dir`), háčky jsou vypnuté
a MCP je prázdné. Nastavení a MCP jdou do souborů v `brain/`, ne do řádky (cmd.exe láme uvozovky v JSON).
"""
import json
import os
import shutil
import uuid
from pathlib import Path

HEART_DIR = Path(__file__).resolve().parent
PROMPT_FILE = HEART_DIR / "prompt.md"
TOOL_FILE = HEART_DIR / "opora_heart.py"
TOOL_NAME = "opora_heart.py"  # kopie v cwd (`brain/`), aby pravidlo Bash nemělo v cestě mezery
MODEL, ADVISOR = "haiku", "opus"
MAX_TURNS = 40
# Vestavěné nástroje jen tyto (bez PowerShellu, Edit, Write, Webu); méně definic = menší kontext i porada.
TOOLS = "Read,Grep,Glob,Bash"
ALLOWED_TOOLS = f"Read,Grep,Glob,Bash(python {TOOL_NAME}:*)"
STRIPPED = ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "CELERIS_API_KEY")
SECRETS = ("Read(**/.env)", "Read(**/.env.*)", "Read(**/*.pem)", "Read(**/*.key)")
SETTINGS_FILE, MCP_FILE = "heart-settings.json", "heart-mcp.json"


def find_claude(which=shutil.which, nt=None):
    """Spustitelný `claude`; na Windows nejdřív `claude.exe`, pak `claude.cmd`. None, když chybí."""
    names = ("claude.exe", "claude.cmd", "claude") if (os.name == "nt" if nt is None else nt) else ("claude",)
    for name in names:
        found = which(name)
        if found:
            return found
    return None


def rule_path(path):
    """Absolutní cesta ve tvaru pravidel Claude Code: `//c/...` na Windows, `//...` jinde."""
    text = str(Path(path).resolve()).replace("\\", "/")
    if len(text) > 1 and text[1] == ":":
        text = "/" + text[0].lower() + text[2:]
    return "/" + text if text.startswith("/") else "//" + text


def settings(source_root=None):
    """Nastavení dávky: deny (tajemství, NotebookEdit, zápis do zdroje projektu) a vypnuté háčky."""
    deny = [*SECRETS, "NotebookEdit"]
    if source_root:
        root = rule_path(source_root)
        deny += [f"Edit({root}/**)", f"Write({root}/**)", f"NotebookEdit({root}/**)"]
    return {"disableAllHooks": True, "permissions": {"deny": deny}}


def write_config(brain, source_root=None):
    """Zapíše nastavení a prázdné MCP do `brain/` a zkopíruje tam nástroj; vrací `(settings, mcp)` cesty."""
    brain = Path(brain)
    brain.mkdir(parents=True, exist_ok=True)
    settings_path, mcp_path = brain / SETTINGS_FILE, brain / MCP_FILE
    settings_path.write_text(json.dumps(settings(source_root), ensure_ascii=False, indent=1), encoding="utf-8")
    mcp_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    shutil.copyfile(TOOL_FILE, brain / TOOL_NAME)
    return settings_path, mcp_path


def build_command(claude, *, session_id, resume, settings_path, mcp_path, source_root=None, prompt_file=PROMPT_FILE,
                  max_turns=MAX_TURNS, advisor=True):
    """Řádka §2. Zpráva dávky jde na stdin (`-p` bez pozičního argumentu), ne do řádky (limit délky Windows)."""
    if not session_id:
        raise ValueError("Dávka potřebuje ID relace.")
    uuid.UUID(str(session_id))  # --session-id i --resume berou UUID
    command = [claude, "-p", "--output-format", "json", "--model", MODEL, *(["--advisor", ADVISOR] if advisor else []),
               *(["--resume", session_id] if resume else ["--session-id", session_id]),
               "--setting-sources", "project", "--settings", str(settings_path),
               "--strict-mcp-config", "--mcp-config", str(mcp_path),
               "--tools", TOOLS, "--allowedTools", ALLOWED_TOOLS, "--permission-mode", "dontAsk",
               # Vlastní systémový prompt místo výchozího: poradce dostává celý kontext, takže každý
               # ušetřený token zlevní poradu (smoke 2026-10-29: 193k vstupních tokenů za 6 kol).
               "--system-prompt-file", str(prompt_file), "--disable-slash-commands"]
    if source_root:
        command += ["--add-dir", str(source_root)]
    return command + ["--max-turns", str(max_turns)]


def child_env(*, base_url, token, project, workspace, environ=None):
    """Prostředí procesu bez klíčů API, s adresou instance, tokenem srdce, projektem a pracovním prostorem."""
    env = dict(os.environ if environ is None else environ)
    for key in STRIPPED:
        env.pop(key, None)
    env.update({"OPORA_BASE_URL": base_url, "OPORA_HEART_TOKEN": token, "OPORA_PROJECT": project,
                "OPORA_WORKSPACE": workspace, "PYTHONIOENCODING": "utf-8"})
    return env
