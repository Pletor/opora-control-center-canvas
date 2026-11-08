"""Příkazová řádka a prostředí jedné dávky srdce (docs/brain-heart.md §2).

Srdce běží jako jednorázový `claude -p` pod předplatným: Haiku jako hlavní model, Opus jako poradce.
Z prostředí se odstraní klíče API (běh se nesmí potichu účtovat přes API). Srdce čte, volá svůj nástroj
`opora_heart.py` a píše jen do dílny `brain/dilna/scripts/**` a `brain/dilna/out/**` (§3b): `dontAsk` odmítne
vše mimo povolení, Write/Edit jsou povolené jen pravidly `allow` v nastavení s absolutní cestou dílny
(v `--allowedTools` by mezera v cestě rozdělila pravidlo). Deny pravidla jsou druhá pojistka nad zdrojem projektu
(`--add-dir`) a nad zbytkem `brain/`, háčky jsou vypnuté a MCP je prázdné. Nastavení a MCP jdou do souborů
v `brain/`, ne do řádky (cmd.exe láme uvozovky v JSON).
Systémový prompt a postupy režimů jsou skilly v Brainu (`backend/brain/`, §3.4): dávka bere aktivní verzi
`opora:brain:skill:heart` a skilly režimů `MODE_SKILLS` (`heart_skills`) a zapíše je do `brain/` projektu.
"""
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.agi_pletor.pletor_opora_settings import skills_store
from backend.brain import registry
from backend.brain.store import Store
from backend.brain_opora.heart.opora_research_map import RUNTIME_GUIDANCE

HEART_DIR = Path(__file__).resolve().parent
PROMPT_NAME = "heart-prompt.md"  # aktivní verze skillu `heart` z Brainu, v `brain/` projektu
HEART_SKILL = "opora:brain:skill:heart"
TOOL_FILE = HEART_DIR / "opora_heart.py"
TOOL_NAME = "opora_heart.py"  # kopie v cwd (`brain/`), aby pravidlo Bash nemělo v cestě mezery
RLM_FILE = HEART_DIR / "rlm.py"
# Postupy režimů (docs/navrhy/2026-10-30-vyslech-srdce.md §5): skilly Brainu zapsané do `brain/skills/NAME.md`,
# srdce je čte jen na vyžádání (`opora_heart.py skill NAME`), do systémového promptu se nevkládají.
SKILLS_NAME = "skills"
MODE_SKILLS = {"vyslech": "opora:brain:skill:vyslech", "proces-na-platne": "opora:brain:skill:proces-na-platne"}
# Moduly vedle nástroje: výzkum a duel (§3c, §3d: příkaz, stůl, digest, stažení a ověření, přepis videa, duel), záměr stránky, design systém webu a knihovna pláten toku.
RESEARCH_NAMES = ("opora_research.py", "opora_research_map.py", "research_alternatives.py", "research_actions.py", "research_desk.py", "research_digest.py", "research_fetch.py",
                  "research_verify.py", "research_browser.py", "research_youtube.py", "opora_duel.py", "opora_intent.py",
                  "opora_site.py", "opora_library.py", "opora_library_nodes.py")
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


@dataclass(frozen=True)
class HeartSkills:
    prompt: str  # tělo skillu `heart` (systémový prompt)
    modes: dict  # {jméno režimu: tělo skillu}; včetně postupů z Dílny
    pins: dict  # {jméno skillu: pin `opora:brain:skill:<name>@<sha12>`}
    extras: dict = field(default_factory=dict)  # {jméno postupu z Dílny (`agent: srdce`): popis} – nabídka v dávce


def skill_body(text):
    """Text `SKILL.md` bez úvodního YAML frontmatteru."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:]
    return text


def heart_skills(db, data_root, dilna=None):
    """Aktivní verze skillů srdce z Brainu (registr → git); bez aktivní verze chyba, žádná záloha v souboru.
    K režimům přidá postupy z Dílny s `agent: srdce` (`dilna` = `skills_store.skills_for("srdce")`), bez pinu."""
    store, bodies, pins = Store(data_root), {}, {}
    for name, artifact in {"heart": HEART_SKILL, **MODE_SKILLS}.items():
        active = registry.active(db, artifact)
        if active is None:
            raise RuntimeError(f"Brain nemá aktivní verzi {artifact}.")
        bodies[name] = skill_body(store.read(active["plugin"], active["content_ref"], active["version"]))
        pins[name] = active["pin"]
    prompt = bodies.pop("heart")
    extras = {}
    for name, skill in (skills_store.skills_for("srdce") if dilna is None else dilna).items():
        if name not in bodies:  # režim Brainu má přednost před stejnojmenným postupem Dílny
            bodies[name], extras[name] = skill["body"], skill["description"]
    return HeartSkills(prompt, bodies, pins, extras)


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


def write_config(brain, skills, source_root=None):
    """Zapíše nastavení a prázdné MCP do `brain/`, systémový prompt (`heart-prompt.md`) a postupy režimů
    (`skills/NAME.md`) z `HeartSkills`, zkopíruje tam nástroj s moduly výzkumu a duelu a do dílny `rlm.py` a MCP
    výzkumníka `rea-mcp.json` (se složkami `data/`, `scripts/`, `out/`); vrací `(settings, mcp, prompt)` cesty."""
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
    prompt_path = brain / PROMPT_NAME
    prompt_path.write_bytes((skills.prompt + RUNTIME_GUIDANCE).encode("utf-8"))
    (brain / SKILLS_NAME).mkdir(exist_ok=True)
    for name, text in skills.modes.items():
        (brain / SKILLS_NAME / f"{name}.md").write_bytes(text.encode("utf-8"))
    (brain / DILNA / REA_MCP_NAME).write_text(json.dumps(REA_MCP, indent=1), encoding="utf-8")
    return settings_path, mcp_path, prompt_path


def allowed_tools(subcommands=None):
    """`--allowedTools`: bez výčtu celý nástroj srdce, jinak jen jeho vyjmenované podpříkazy (uzel `tool.opora_heart`)."""
    if subcommands is None:
        return ALLOWED_TOOLS
    return ",".join(["Read", "Grep", "Glob", *(f"Bash(python {TOOL_NAME} {name}:*)" for name in subcommands)])


def build_command(claude, *, session_id, resume, settings_path, mcp_path, prompt_file, source_root=None,
                  max_turns=MAX_TURNS, advisor=True, model=MODEL, advisor_model=ADVISOR, subcommands=None, effort=None):
    """Řádka §2. Zpráva dávky jde na stdin (`-p` bez pozičního argumentu), ne do řádky (limit délky Windows).
    `model`, `advisor_model` a `subcommands` nastavuje uzel `agent.claude` enginu toků; výchozí = dnešní srdce."""
    if not session_id:
        raise ValueError("Dávka potřebuje ID relace.")
    uuid.UUID(str(session_id))  # --session-id i --resume berou UUID
    # `stream-json` (s `--verbose`) nese `usage` každého tahu: rotace relace měří kontext posledního tahu
    # (`session.context_tokens`); poslední řádek proudu je tentýž objekt výsledku jako u `json`.
    command = [claude, "-p", "--output-format", "stream-json", "--verbose", "--model", model, *(["--effort", effort] if effort else []), *(["--advisor", advisor_model] if advisor else []),
               *(["--resume", session_id] if resume else ["--session-id", session_id]),
               "--setting-sources", "project", "--settings", str(settings_path),
               "--strict-mcp-config", "--mcp-config", str(mcp_path),
               "--tools", TOOLS, "--allowedTools", allowed_tools(subcommands), "--permission-mode", "dontAsk",
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
                "BASH_DEFAULT_TIMEOUT_MS": BASH_TIMEOUT_MS, "BASH_MAX_TIMEOUT_MS": BASH_TIMEOUT_MS,
                # ponytail (plugin pro psaní kódu dělníků) srdce nemění: plánuje, nepíše kód; zapnout až po evalu
                "PONYTAIL_DEFAULT_MODE": "off"})
    if source_root:
        env["OPORA_SOURCE_ROOT"] = str(source_root)
    return env
