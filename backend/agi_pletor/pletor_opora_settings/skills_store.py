"""Dílna: skilly jako soubory v `skills/<nazev>/` (SKILL.md, `scripts/*.py`, `references/*.md`).

Kontrakt: docs/navrhy/2026-11-05-dilna-skillu.md §3, §5. Zápis jen dovnitř složky skillu, jen textové přípony.
shortcut: skilly leží v repu, ne v Brainu; kandidát, verze a aktivace přijdou s D4.
"""
import re
from pathlib import Path

SKILLS = Path(__file__).parent / "skills"
NAME = re.compile(r"^[a-z][a-z0-9-]*$")
PATH = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")  # relativní, lomítka, bez `\`, `:` a mezer
SUFFIXES = {".md", ".py", ".json", ".txt", ".yaml"}
MAX_CONTENT = 200_000

TEMPLATE = """---
name: {name}
description: ""
---

# {name}

## Kdy použít

## Postup

## Ověření
"""


def _skill(root, name, exists=True):
    if not NAME.match(name or ""):
        raise ValueError("Název skillu je [a-z][a-z0-9-]*.")
    folder = Path(root) / name
    if exists and not (folder / "SKILL.md").is_file():
        raise LookupError(f"Skill {name} neexistuje.")
    return folder


def _target(folder, path):
    """Cesta souboru uvnitř skillu; mimo složku, symlink nebo jiná přípona je `ValueError`."""
    if not isinstance(path, str) or not PATH.match(path) or any(part in (".", "..") for part in path.split("/")):
        raise ValueError("Cesta je relativní uvnitř skillu, bez `..` (např. scripts/restart.py).")
    if Path(path).suffix not in SUFFIXES:
        raise ValueError(f"Povolené přípony: {', '.join(sorted(SUFFIXES))}.")
    target = folder / path
    node = target
    while node != folder:
        if node.is_symlink():
            raise ValueError("Symlink ve skillu Dílna nečte ani nezapisuje.")
        node = node.parent
    if not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Cesta vede mimo složku skillu.")
    return target


AGENTS = ("pletor", "srdce")  # frontmatter `agent:` = kdo skill dostává (Pletor do promptu, srdce mezi postupy)


def _front(text, key):
    """Hodnota klíče z úvodního YAML frontmatteru (jen jednořádkové hodnoty), jinak ''."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(key + ":"):
            return line.removeprefix(key + ":").strip().strip("\"'")
    return ""


def _description(text):
    return _front(text, "description")


def _body(text):
    """Text `SKILL.md` bez frontmatteru."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:]
    return text


def _files(folder):
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and not p.is_symlink())


def _read_all(root):
    for folder in sorted(Path(root).glob("*/SKILL.md")):
        folder = folder.parent
        if NAME.match(folder.name):
            yield folder, (folder / "SKILL.md").read_text(encoding="utf-8", errors="replace")


def list_skills(root=SKILLS):
    """Skilly ve složce: `[{name, description, agent, files}]`; složka bez SKILL.md nebo se špatným názvem se přeskočí."""
    return [{"name": folder.name, "description": _description(text), "agent": _front(text, "agent"), "files": _files(folder)}
            for folder, text in _read_all(root)]


def skills_for(agent, root=SKILLS):
    """Skilly daného příjemce (`agent: pletor|srdce`): `{name: {description, body}}` v pořadí názvů."""
    return {folder.name: {"description": _description(text), "body": _body(text)}
            for folder, text in _read_all(root) if _front(text, "agent") == agent}


def create_skill(root, name):
    """Založí `<name>/SKILL.md` ze šablony → `{name, files}`; existující skill je `FileExistsError`."""
    folder = _skill(root, name, exists=False)
    if folder.exists():
        raise FileExistsError(f"Skill {name} už existuje.")
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(TEMPLATE.format(name=name), encoding="utf-8", newline="")
    return {"name": name, "files": _files(folder)}


def read_file(root, name, path):
    target = _target(_skill(root, name), path)
    if not target.is_file():
        raise LookupError(f"Soubor {path} ve skillu {name} neexistuje.")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


def write_file(root, name, path, content):
    """Zapíše textový soubor skillu (chybějící podsložky vytvoří) → `{path, bytes}`."""
    target = _target(_skill(root, name), path)
    if not isinstance(content, str) or len(content) > MAX_CONTENT or "\0" in content:
        raise ValueError(f"Obsah je text do {MAX_CONTENT} znaků bez nulového znaku.")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    target.write_bytes(data)
    return {"path": path, "bytes": len(data)}
