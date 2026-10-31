"""Posun worktree za main (docs/domeny-a-worktree.md, „Posun worktree za main“): jen bezpečný fast-forward."""
import subprocess
from pathlib import Path

from backend.integrations.gitio import git

TIMEOUT = 20


def fast_forward(root, main_sha):
    """Posune worktree `root` na `main_sha` a vrátí nové HEAD; nic neposunuto (chybí, špinavý, vlastní commity,
    shodné HEAD, nečitelné) = None. Nikdy `--force` ani `reset`."""
    if root is None or not Path(root).is_dir() or not main_sha:
        return None
    try:
        if git(root, "status", "--porcelain", timeout=TIMEOUT, optional=True) != "":
            return None  # None = nečitelné, neprázdné = změny
        head = git(root, "rev-parse", "HEAD", timeout=TIMEOUT, optional=True)
        if not head or head == main_sha:
            return None
        # `is-ancestor` vrací 1 pro ne-předka; optional=True to převede na None, což stačí.
        if git(root, "merge-base", "--is-ancestor", head, main_sha, timeout=TIMEOUT, optional=True) is None:
            return None
        git(root, "merge", "--ff-only", main_sha, timeout=TIMEOUT, optional=True)
        new = git(root, "rev-parse", "HEAD", timeout=TIMEOUT, optional=True)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return new if new == main_sha else None
