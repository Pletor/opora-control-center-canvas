"""Katalog skills, které má Claude Code na tomto počítači k dispozici.

Čte jen `SKILL.md` (název a popis z frontmatteru), nic nespouští a nic nemění.
Zdroje: skills projektu (`.claude/skills`), uživatele (`~/.claude/skills`)
a instalované marketplace pluginy (`~/.claude/plugins/marketplaces`).
"""

from pathlib import Path

MAX_DESCRIPTION = 300
PLUGIN_PATTERNS = ("*/skills/*/SKILL.md", "*/.claude/skills/*/SKILL.md", "*/plugins/*/skills/*/SKILL.md")


def default_roots(repo_root: Path, home: Path | None = None) -> dict[str, Path]:
    home = home or Path.home()
    return {
        "project": repo_root / ".claude" / "skills",
        "user": home / ".claude" / "skills",
        "plugins": home / ".claude" / "plugins" / "marketplaces",
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    """Ploché `klíč: hodnota` řádky mezi `---`; uvozovky se odstraní, blokové `>`/`|` se spojí do jedné věty."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    block_key: str | None = None
    block: list[str] = []

    def flush():
        nonlocal block_key, block
        if block_key is not None:
            out[block_key] = " ".join(part.strip() for part in block if part.strip())
        block_key, block = None, []

    for line in lines[1:]:
        if line.strip() == "---":
            break
        if block_key is not None and (line.startswith((" ", "\t")) or not line.strip()):
            block.append(line)
            continue
        flush()
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value in (">", "|", ">-", "|-", ">+", "|+"):
            block_key = key.strip()
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    flush()
    return out


def read_skill(path: Path, scope: str) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:20000]
    except OSError:
        return None
    meta = parse_frontmatter(text)
    name = meta.get("name") or path.parent.name
    description = meta.get("description", "")
    if len(description) > MAX_DESCRIPTION:
        description = description[: MAX_DESCRIPTION - 1].rstrip() + "…"
    return {
        "id": f"{scope}:{name}",
        "name": name,
        "description": description,
        "scope": scope,
        "path": str(path.parent),
    }


def list_skills(roots: dict[str, Path]) -> list[dict]:
    found: dict[str, dict] = {}

    def add(path: Path, scope: str):
        item = read_skill(path, scope)
        if item and item["id"] not in found:
            found[item["id"]] = item

    for scope in ("project", "user"):
        root = roots.get(scope)
        if root and root.is_dir():
            for entry in sorted(root.iterdir()):
                skill = entry / "SKILL.md"
                if skill.is_file():
                    add(skill, scope)
    plugins = roots.get("plugins")
    if plugins and plugins.is_dir():
        for pattern in PLUGIN_PATTERNS:
            for skill in sorted(plugins.glob(pattern)):
                marketplace = skill.relative_to(plugins).parts[0]
                add(skill, f"plugin:{marketplace}")
    return sorted(found.values(), key=lambda item: (item["scope"] != "project", item["scope"] != "user", item["scope"], item["name"].casefold()))
