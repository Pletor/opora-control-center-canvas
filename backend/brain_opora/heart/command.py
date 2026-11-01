"""Příkazová řádka a prostředí jedné dávky srdce (docs/brain-heart.md §2).

Srdce běží jako jednorázový `claude -p` pod předplatným: Haiku jako hlavní model, Opus jako poradce.
Z prostředí se odstraní klíče API (běh se nesmí potichu účtovat přes API). Srdce čte, volá svůj nástroj
`opora_heart.py` a píše jen do dílny `brain/dilna/scripts/**` a `brain/dilna/out/**` (§3b): `dontAsk` odmítne
vše mimo povolení, Write/Edit jsou povolené jen pravidly `allow` v nastavení s absolutní cestou dílny
(v `--allowedTools` by mezera v cestě rozdělila pravidlo). Deny pravidla jsou druhá pojistka nad zdrojem projektu
(`--add-dir`) a nad zbytkem `brain/`, háčky jsou vypnuté a MCP je prázdné. Nastavení a MCP jdou do souborů
v `brain/`, ne do řádky (cmd.exe láme uvozovky v JSON).
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
RLM_FILE = HEART_DIR / "rlm.py"
# Postupy režimů (docs/navrhy/2026-10-30-vyslech-srdce.md §5): v `brain/skills/`, srdce je čte jen na vyžádání
# (`opora_heart.py skill NAME`), do systémového promptu se nevkládají.
SKILLS_DIR, SKILLS_NAME = HEART_DIR / "skills", "skills"
# Výzkum a duel vedle nástroje (§3c, §3d): příkaz, stůl, digest, stažení a ověření, duel.
RESEARCH_NAMES = ("opora_research.py", "research_desk.py", "research_digest.py", "research_fetch.py",
                  "research_verify.py", "research_browser.py", "opora_duel.py")
DILNA, RLM_NAME, DILNA_DIRS = "dilna", "rlm.py", ("data", "scripts", "out")
WRITABLE = ("scripts", "out")  # jediné složky, kam srdce smí Write/Edit
MODEL, ADVISOR = "haiku", "opus"
MAX_TURNS = 40
# Vestavěné nástroje jen tyto (bez PowerShellu, Webu); méně definic = menší kontext i porada.
# Write a Edit jsou tu kvůli skriptům dílny; povolené jsou jen v `allow` nastavení (`settings`).
TOOLS = "Read,Grep,Glob,Bash,Write,Edit"
ALLOWED_TOOLS = f"Read,Grep,Glob,Bash(python {TOOL_NAME}:*)"
STRIPPED = ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "CELERIS_API_KEY")
SECRETS = ("Read(**/.env)", "Read(**/.env.*)", "Read(**/*.pem)", "Read(**/*.key)")
SETTINGS_FILE, MCP_FILE = "heart-settings.json", "heart-mcp.json"
# MCP výzkumníka (§3c): jen server REA, stejná definice jako `.agent-office/rea-mcp.json` v kořeni repozitáře
# (kořen zdroje projektu může být jinde, proto kopie tady). Srdce samo REA nikdy nenačítá.
REA_MCP_NAME = "rea-mcp.json"
REA_MCP = {"mcpServers": {"rea": {"type": "stdio", "command": "cmd",
                                  "args": ["/c", "npx", "-y", "rea-agents@6.7.0", "mcp"]}}}
# Výzkum běží až 10 min (stůl má strop 600 s) a duel kolem 9 min: Bash srdce musí počkat déle než výchozí 2 min.
BASH_TIMEOUT_MS = "700000"


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


def workshop_allow(brain):
    """Povolení zápisu srdce: Write a Edit jen pod `dilna/scripts/**` a `dilna/out/**` (§3b)."""
    dilna = rule_path(Path(brain) / DILNA)
    return [f"{tool}({dilna}/{folder}/**)" for tool in ("Write", "Edit") for folder in WRITABLE]


def workshop_deny(brain):
    """Druhá pojistka: soubory `brain/` a dílny mimo skripty a výstupy (stav, deník, nástroje, data `ctx`)."""
    root, dilna = rule_path(brain), rule_path(Path(brain) / DILNA)
    paths = [f"{root}/*.{ext}" for ext in ("json", "jsonl", "py", "txt", "md")]
    paths += [f"{dilna}/*.py", f"{dilna}/*.json", f"{dilna}/*.jsonl", f"{dilna}/data/**"]
    return [f"{tool}({path})" for tool in ("Write", "Edit") for path in paths]


def settings(source_root=None, brain=None):
    """Nastavení dávky: allow dílny, deny (tajemství, NotebookEdit, zdroj projektu, zbytek `brain/`), bez háčků."""
    deny, allow = [*SECRETS, "NotebookEdit"], []
    if source_root:
        root = rule_path(source_root)
        deny += [f"Edit({root}/**)", f"Write({root}/**)", f"NotebookEdit({root}/**)"]
    if brain:
        allow, deny = workshop_allow(brain), deny + workshop_deny(brain)
    return {"disableAllHooks": True, "permissions": {"allow": allow, "deny": deny}}


def write_config(brain, source_root=None):
    """Zapíše nastavení a prázdné MCP do `brain/`, zkopíruje tam nástroj s moduly výzkumu a duelu, postupy režimů
    (`skills/*.md`) a do dílny `rlm.py` a MCP výzkumníka `rea-mcp.json` (se složkami `data/`, `scripts/`, `out/`);
    vrací `(settings, mcp)` cesty."""
    brain = Path(brain)
    brain.mkdir(parents=True, exist_ok=True)
    for folder in DILNA_DIRS:
        (brain / DILNA / folder).mkdir(parents=True, exist_ok=True)
    settings_path, mcp_path = brain / SETTINGS_FILE, brain / MCP_FILE
    settings_path.write_text(json.dumps(settings(source_root, brain), ensure_ascii=False, indent=1), encoding="utf-8")
    mcp_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    shutil.copyfile(TOOL_FILE, brain / TOOL_NAME)
    for name in RESEARCH_NAMES:
        shutil.copyfile(HEART_DIR / name, brain / name)
    shutil.copyfile(RLM_FILE, brain / DILNA / RLM_NAME)
    (brain / SKILLS_NAME).mkdir(exist_ok=True)
    for skill in SKILLS_DIR.glob("*.md"):
        shutil.copyfile(skill, brain / SKILLS_NAME / skill.name)
    (brain / DILNA / REA_MCP_NAME).write_text(json.dumps(REA_MCP, indent=1), encoding="utf-8")
    return settings_path, mcp_path


def build_command(claude, *, session_id, resume, settings_path, mcp_path, source_root=None, prompt_file=PROMPT_FILE,
                  max_turns=MAX_TURNS, advisor=True):
    """Řádka §2. Zpráva dávky jde na stdin (`-p` bez pozičního argumentu), ne do řádky (limit délky Windows)."""
    if not session_id:
        raise ValueError("Dávka potřebuje ID relace.")
    uuid.UUID(str(session_id))  # --session-id i --resume berou UUID
    # `stream-json` (s `--verbose`) nese `usage` každého tahu: rotace relace měří kontext posledního tahu
    # (`session.context_tokens`); poslední řádek proudu je tentýž objekt výsledku jako u `json`.
    command = [claude, "-p", "--output-format", "stream-json", "--verbose", "--model", MODEL, *(["--advisor", ADVISOR] if advisor else []),
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


def child_env(*, base_url, token, project, workspace, source_root=None, environ=None):
    """Prostředí procesu bez klíčů API, s adresou instance, tokenem srdce, projektem, pracovním prostorem
    a kořenem zdroje (`OPORA_SOURCE_ROOT` pro `rlm.py`; bez zdroje chybí)."""
    env = dict(os.environ if environ is None else environ)
    for key in (*STRIPPED, "OPORA_SOURCE_ROOT"):
        env.pop(key, None)
    env.update({"OPORA_BASE_URL": base_url, "OPORA_HEART_TOKEN": token, "OPORA_PROJECT": project,
                "OPORA_WORKSPACE": workspace, "PYTHONIOENCODING": "utf-8",
                "BASH_DEFAULT_TIMEOUT_MS": BASH_TIMEOUT_MS, "BASH_MAX_TIMEOUT_MS": BASH_TIMEOUT_MS})
    if source_root:
        env["OPORA_SOURCE_ROOT"] = str(source_root)
    return env
