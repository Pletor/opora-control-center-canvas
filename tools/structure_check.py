"""Najde soubory a složky, které porušují pravidla umístění z docs/pravidla-struktury.md.

Každý nález je (pravidlo, cesta, věta). Pravidla jsou mechanická, aby je šlo hledat Globem:
.tsx leží v `components/`, .ts v `logic/` (test i vedle komponenty), .css ve `styles/`;
žádné složky `tests/`; router jen v `backend/api/`; žádné názvy bez obsahu (utils, helpers…);
feature složka a balíček mají README; zdrojový soubor má nejvýš zhruba 200 řádků.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SOURCE_ROOTS = ("frontend", "backend", "database", "tools")

SKIP_DIRS = ("node_modules", "dist", "__pycache__", ".venv", "vendor")

DRAWERS = ("components", "logic", "styles")

VAGUE_NAMES = ("utils", "util", "misc", "common", "helpers", "helper")

MAX_LINES = 200

_ROUTER_RE = re.compile(r"\bAPIRouter\(")


def _files(root: Path, top: str) -> list[Path]:
    base = root / top
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file()
                  and not any(part in SKIP_DIRS for part in p.relative_to(root).parts))


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test(name: str) -> bool:
    return name.startswith("test_") or ".test." in name


def check_drawers(root: Path) -> list[tuple[str, str, str]]:
    """Soubor frontendu leží v šuplíku svého druhu."""
    found = []
    for path in _files(root, "frontend"):
        parent, name = path.parent.name, path.name
        if name.endswith(".tsx") and parent != "components":
            found.append(("supliky", _rel(path, root), ".tsx patří do components/"))
        elif name.endswith(".ts") and not name.endswith(".d.ts"):
            allowed = ("logic", "components") if _is_test(name) else ("logic",)
            if parent not in allowed:
                found.append(("supliky", _rel(path, root), ".ts patří do logic/"))
        elif name.endswith(".css") and parent != "styles":
            found.append(("supliky", _rel(path, root), ".css patří do styles/"))
    return found


def check_test_dirs(root: Path) -> list[tuple[str, str, str]]:
    """Test leží vedle toho, co testuje; složky tests/ nevznikají."""
    dirs = set()
    for top in SOURCE_ROOTS:
        for path in _files(root, top):
            for parent in path.relative_to(root).parents:
                if parent.name in ("tests", "test", "__tests__"):
                    dirs.add(parent.as_posix())
    return [("testy-vedle", d, "test patří vedle modulu, ne do složky tests/") for d in sorted(dirs)]


def check_routers(root: Path) -> list[tuple[str, str, str]]:
    """Router vzniká jen v backend/api/<prostředí>/."""
    found = []
    for path in _files(root, "backend"):
        rel = _rel(path, root)
        if path.suffix != ".py" or rel.startswith("backend/api/") or _is_test(path.name):
            continue
        if _ROUTER_RE.search(path.read_text(encoding="utf-8", errors="replace")):
            found.append(("router-v-api", rel, "APIRouter patří do backend/api/<prostředí>/"))
    return found


def check_names(root: Path) -> list[tuple[str, str, str]]:
    """Název říká, co dělá; žádné šuplíky bez obsahu."""
    seen = set()
    for top in SOURCE_ROOTS:
        for path in _files(root, top):
            rel = path.relative_to(root)
            for part in (*rel.parent.parts, path.stem):
                if part.lower() in VAGUE_NAMES:
                    seen.add(rel.as_posix())
    return [("nazev", p, "název bez obsahu (utils, helpers, common…)") for p in sorted(seen)]


def check_readmes(root: Path) -> list[tuple[str, str, str]]:
    """Feature složka frontendu a balíček backendu mají README."""
    folders = set()
    for path in _files(root, "frontend"):
        if path.parent.name in DRAWERS:
            folders.add(path.parent.parent)
    for top in ("backend", "database"):
        for path in _files(root, top):
            if path.name == "__init__.py":
                folders.add(path.parent)
    return [("readme", _rel(d, root), "složka nemá README.md")
            for d in sorted(folders) if not (d / "README.md").is_file()]


def check_lengths(root: Path) -> list[tuple[str, str, str]]:
    """Zdrojový soubor (mimo testy) se nad zhruba 200 řádků dělí na další dílek."""
    found = []
    for top in ("frontend", "backend", "database"):
        for path in _files(root, top):
            if path.suffix not in (".ts", ".tsx", ".css", ".py") or _is_test(path.name):
                continue
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            if lines > MAX_LINES:
                found.append(("delka", _rel(path, root), f"{lines} řádků, víc než {MAX_LINES}"))
    return found


CHECKS = (check_drawers, check_test_dirs, check_routers, check_names, check_readmes, check_lengths)


def check_repo(root: Path) -> list[tuple[str, str, str]]:
    root = Path(root)
    return [finding for check in CHECKS for finding in check(root)]


def counts(findings) -> dict[str, int]:
    result: dict[str, int] = {}
    for rule, _path, _why in findings:
        result[rule] = result.get(rule, 0) + 1
    return result


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    findings = check_repo(root)
    for rule, path, why in findings:
        print(f"{rule}\t{path}\t{why}")
    print(f"nálezů: {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
