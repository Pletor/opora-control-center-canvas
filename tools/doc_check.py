"""Najde v dokumentaci odkazy na cesty, které v repozitáři neexistují."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = (
    "node_modules",
    "dist",
    ".git",
    ".data",
    ".venv",
    ".venv-graphify",
    "graphify-out",
    ".worktrees",
    ".hermes",
    "__pycache__",
    "vendor",
)

_REPO_PATH_EXTENSIONS = (
    ".py",
    ".ts",
    ".tsx",
    ".css",
    ".md",
    ".json",
    ".toml",
    ".mjs",
    ".sqlite",
)

_WILDCARD_CHARS = ("<", ">", "*", "{", "}", "?", "…")

# Odkaz na místo v kódu se píše jako `soubor.py:123` nebo `soubor.py:123-140`.
_LINE_SUFFIX_RE = re.compile(r":\d+(-\d+)?$")

# První segment, který nikdy neznamená složku v repozitáři: MIME typy a git reference.
_NOT_FOLDERS = ("application", "text", "image", "audio", "video", "font", "refs")

_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return any(part in SKIP_DIRS for part in rel.parts)


def markdown_files(root: Path) -> list[Path]:
    """Všechny .md v repozitáři mimo SKIP_DIRS, seřazené."""
    root = Path(root)
    files = [p for p in root.rglob("*.md") if not _is_skipped(p, root)]
    return sorted(files)


def _clean_ref(raw: str) -> str:
    ref = raw.split()[0] if raw.strip() else ""
    # `soubor.py::test_neco` je adresa testu, ne cesta; kontroluje se jen soubor.
    ref = ref.split("::", 1)[0]
    ref = ref.split("#", 1)[0]
    ref = _LINE_SUFFIX_RE.sub("", ref)
    ref = ref.rstrip(".,;:")
    return ref.strip()


def collect_references(text: str) -> list[tuple[int, str]]:
    """(číslo řádku, odkaz) pro markdown odkazy [x](cesta) a cesty v jednoduchých zpětných apostrofech."""
    refs: list[tuple[int, str]] = []
    in_code_block = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for match in _MARKDOWN_LINK_RE.finditer(line):
            cleaned = _clean_ref(match.group(1))
            if cleaned:
                refs.append((lineno, cleaned))
        for match in _BACKTICK_RE.finditer(line):
            cleaned = _clean_ref(match.group(1))
            if cleaned:
                refs.append((lineno, cleaned))
    return refs


def is_repo_path(ref: str) -> bool:
    """Vypadá to jako konkrétní cesta v repozitáři?

    Jedno jméno se lomítkem (`logic/`) je konvence, ne umístění, a nekontroluje se.
    Odmítnuty jsou i routy, cesty mimo repozitář, MIME typy a git reference.
    """
    if not ref:
        return False
    if ref.startswith(("http://", "https://", "mailto:", "#", "/", "~", "../")):
        return False
    if any(ch in ref for ch in _WILDCARD_CHARS):
        return False
    segments = [part for part in re.split(r"[\\/]", ref) if part]
    if not segments:
        return False
    if segments[0] in _NOT_FOLDERS:
        return False
    if any(part in SKIP_DIRS for part in segments):
        return False
    # Samotné jméno souboru je zmínka, ne odkaz na místo; cesta musí mít aspoň dva díly.
    return len(segments) > 1


def _exists_relative(base: Path, ref: str) -> bool:
    try:
        return (base / ref).exists()
    except OSError:
        return False


def _bases(root: Path, doc: Path) -> list[Path]:
    # README uvnitř frontendu píše cesty od kořene frontendu, skill od kořene skillu.
    # Odkaz proto platí, když sedí proti kterékoli nadřazené složce až ke kořeni repozitáře.
    bases = []
    current = doc.parent
    while True:
        bases.append(current)
        if current == root or current.parent == current:
            break
        current = current.parent
    return bases


def check_file(root: Path, doc: Path) -> list[dict]:
    """[{"doc": str, "line": int, "path": str}] pro odkazy, které neexistují."""
    root = Path(root)
    doc = Path(doc)
    text = doc.read_text(encoding="utf-8")
    doc_label = str(doc.relative_to(root)).replace("\\", "/")
    findings = []
    bases = _bases(root, doc)
    top_level = {entry.name for entry in root.iterdir()}
    for lineno, ref in collect_references(text):
        if not is_repo_path(ref):
            continue
        # Bez přípony to musí začínat skutečnou složkou repozitáře, jinak jde o dvojici
        # pojmů oddělenou lomítkem (`GET/POST`, `incoming/outgoing`), ne o cestu.
        if not ref.endswith(_REPO_PATH_EXTENSIONS) and ref.split("/")[0] not in top_level:
            continue
        if any(_exists_relative(base, ref) for base in bases):
            continue
        findings.append({"doc": doc_label, "line": lineno, "path": ref})
    return findings


def check_repo(root: Path) -> list[dict]:
    """Totéž pro všechny dokumenty; seřazené podle dokumentu a řádku."""
    root = Path(root)
    findings: list[dict] = []
    for doc in markdown_files(root):
        findings.extend(check_file(root, doc))
    return sorted(findings, key=lambda item: (item["doc"], item["line"]))


def main(argv=None) -> int:
    """CLI: vypíše nálezy a jejich počet; 0 když je čisto, 1 když ne."""
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    findings = check_repo(root)
    for finding in findings:
        print(f"{finding['doc']}:{finding['line']}: {finding['path']}")
    print(f"Nalezeno odkazů na neexistující cesty: {len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
