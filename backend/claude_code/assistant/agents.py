"""Subagenti asistenta z `agents/*.md` (docs/asistent.md §14.2).

Asistent běží v projektu uživatele a projektové `.claude/agents/` Opory by neviděl, proto definice
nese backend a CLI je dostane přepínačem `--agents <soubor>`. Frontmatter se parsuje tady (řádky
`key: value`, `tools: [A, B]`), aby nevznikla nová závislost.
"""

from __future__ import annotations

from pathlib import Path

AGENTS_DIR = Path(__file__).with_name("agents")
MODELS = ("haiku", "sonnet", "opus")
PREFIX = "opora-"


def _fail(path, message):
    raise ValueError(f"Subagent {Path(path).name}: {message}")


def parse_agent(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        _fail(path, "chybí frontmatter.")
    head, sep, body = text[4:].partition("\n---")
    if not sep:
        _fail(path, "frontmatter není uzavřený.")
    meta = {}
    for line in head.splitlines():
        if not line.strip():
            continue
        key, colon, value = line.partition(":")
        if not colon:
            _fail(path, f"neplatný řádek frontmatteru „{line}“.")
        meta[key.strip()] = value.strip()
    name = meta.get("name", "")
    if name != path.stem or not name.startswith(PREFIX):
        _fail(path, f"name musí být „{path.stem}“ a začínat „{PREFIX}“.")
    if meta.get("model") not in MODELS:
        _fail(path, "model musí být " + ", ".join(MODELS) + ".")
    raw = meta.get("tools", "")
    if not (raw.startswith("[") and raw.endswith("]")):
        _fail(path, "tools musí být seznam ve tvaru [A, B].")
    tools = [item.strip() for item in raw[1:-1].split(",") if item.strip()]
    if not tools:
        _fail(path, "tools nesmí být prázdný.")
    if not meta.get("description"):
        _fail(path, "chybí description.")
    prompt = body.lstrip("\n").strip()
    if not prompt:
        _fail(path, "prompt je prázdný.")
    return name, {"description": meta["description"], "prompt": prompt, "tools": tools, "model": meta["model"]}


def load_agents(directory=None):
    """`{name: {description, prompt, tools, model}}` ze všech `*.md` v adresáři."""
    folder = Path(directory) if directory is not None else AGENTS_DIR
    return dict(parse_agent(path) for path in sorted(folder.glob("*.md")))
