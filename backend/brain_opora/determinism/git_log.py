"""Čtení gitu zdroje pro srdce (docs/brain-heart-orchestrator.md §4): jen `rev-parse` a `log`, nic nemění.

Git běží přes `integrations.gitio.git` (bez shellu, s časovým limitem, bez háčků projektu). Selhání je `ValueError`
nebo `OSError` / `subprocess.SubprocessError`; volající ho polyká (`READ_ERRORS`).
"""
import subprocess

from backend.integrations.gitio import git

TIMEOUT = 15
READ_ERRORS = (ValueError, OSError, subprocess.SubprocessError)


def head(root):
    """Plné sha HEAD pracovního stromu `root`."""
    return git(root, "rev-parse", "HEAD", timeout=TIMEOUT)


def _lines(root, limit, *revisions):
    out = git(root, "log", f"-{int(limit)}", "--abbrev=7", "--format=%h %s", *revisions, timeout=TIMEOUT)
    return [line for line in (out or "").splitlines() if line.strip()]


def between(root, old, new, limit=20):
    """Commity `old..new` od nejnovějšího jako „sha7 titulek“, nejvýš `limit`."""
    return _lines(root, limit, f"{old}..{new}")


def recent(root, limit=10):
    """Posledních `limit` commitů HEAD jako „sha7 titulek“."""
    return _lines(root, limit)
