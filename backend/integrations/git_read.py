"""Čtení historie gitu pro párování commitů kódu se zadáním v aplikaci."""

import subprocess

from backend.integrations.gitio import git

# Oddělovač, který se v commitu nemůže objevit.
SEP = "\x1f"
COMMIT_FORMAT = SEP.join(["%H", "%an", "%aI", "%s", "%(trailers:unfold,only)"])


def _read(root, *args, timeout=15):
    # Pozorování nesmí shodit volajícího: chybějící repozitář, revize i timeout jsou None.
    try:
        return git(root, *args, timeout=timeout, optional=True)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _slash(value):
    # Git mluví lomítky i na Windows.
    return str(value).replace("\\", "/")


def head(root, ref="HEAD"):
    """SHA revize, nebo None, když ref neexistuje."""
    return _read(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") or None


def is_ancestor(root, ancestor, descendant):
    """True, když je `ancestor` předkem `descendant`."""
    # Obal hlásí nenulový návrat jako chybu, proto optional: "" znamená ano, None ne.
    answer = _read(root, "merge-base", "--is-ancestor", str(ancestor), str(descendant))
    return answer is not None


def commits_between(root, base, head_sha, limit=500):
    """SHA commitů v `base..head_sha`, nejnovější první; `base` se nevrací."""
    listing = _read(
        root,
        "rev-list",
        f"--max-count={int(limit)}",
        f"{base}..{head_sha}",
        timeout=30,
    )
    if not listing:
        return []
    return [line.strip() for line in listing.splitlines() if line.strip()]


def recent(root, ref="HEAD", limit=50):
    """SHA posledních commitů dané větve, nejnovější první."""
    listing = _read(root, "rev-list", f"--max-count={int(limit)}", str(ref), timeout=30)
    if not listing:
        return []
    return [line.strip() for line in listing.splitlines() if line.strip()]


def commit_info(root, sha):
    """{"sha", "author", "date", "subject", "trailers": {klíč: [hodnoty]}, "paths": [str]}.

    Vrací None, když revize neexistuje. U merge commitu je seznam cest prázdný,
    protože git pro spojení bez zvolené strany žádný seznam souborů nevypisuje.
    """
    raw = _read(root, "show", "--no-patch", f"--format={COMMIT_FORMAT}", str(sha))
    if not raw:
        return None
    parts = raw.split(SEP)
    if len(parts) < 4:
        return None
    # Bez trailerů končí výpis prázdným polem a obal ho při strip() odřízne.
    parts += [""] * (5 - len(parts))
    return {
        "sha": parts[0].strip(),
        "author": parts[1],
        "date": parts[2],
        "subject": parts[3],
        "trailers": _trailers(parts[4]),
        "paths": _changed_paths(root, sha),
    }


def _trailers(block):
    found = {}
    for line in block.splitlines():
        key, marker, value = line.partition(":")
        if not marker or not key.strip():
            continue
        found.setdefault(key.strip(), []).append(value.strip())
    return found


def changed_paths(root, sha):
    """Cesty změněné commitem (`git show --name-only`); prázdné pole i u neznámé revize."""
    return _changed_paths(root, sha)


def _changed_paths(root, sha):
    listing = _read(root, "show", "--name-only", "--format=", str(sha))
    if not listing:
        return []
    return [line.strip() for line in listing.splitlines() if line.strip()]


def rename_of(root, path, limit=200):
    """Nový název souboru, pokud byl v historii přejmenován; jinak None."""
    wanted = _slash(path)
    # S pathspec git rozpoznávání přejmenování vypne a hlásí jen smazání, proto se
    # prochází přejmenování celé historie a cesta se páruje až tady.
    listing = _read(
        root,
        "log",
        f"--max-count={int(limit)}",
        "--find-renames",
        "--diff-filter=R",
        "--name-status",
        "--format=",
        timeout=30,
    )
    if not listing:
        return None
    # Git řadí od nejnovějšího, takže první shoda je poslední přejmenování.
    for line in listing.splitlines():
        cells = line.split("\t")
        if len(cells) < 3 or not cells[0].startswith("R"):
            continue
        if cells[1].strip() == wanted:
            return cells[2].strip()
    return None


def blob_sha(root, ref, path):
    """SHA obsahu souboru v dané revizi, nebo None."""
    spec = f"{ref}:{_slash(path)}"
    return _read(root, "rev-parse", "--verify", "--quiet", spec) or None
