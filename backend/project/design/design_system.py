"""DESIGN.md projektu (docs/design-nahled.md §2): design systém z commitnuté revize, ne z pracovního stromu.

Kořen je hlavní pracovní strom zdroje projektu (stejný jako pro Graphify a mapy, `main_project_root`).
Čte se `HEAD:DESIGN.md` přes `git cat-file`, takže rozepsané a necommitnuté změny se nikdy neukážou.
Otisk `sha256` je přes celé bajty souboru; `markdown` se ořízne na `MAX_BYTES` a hlásí `truncated`.
Chybějící zdroj, repozitář bez commitu nebo bez DESIGN.md = `{available: false, reason}`, nikdy chyba.
Obsah souboru je pro agenta podklad (data), ne příkaz."""
import hashlib
import re
import subprocess
import threading

from backend.integrations.gitio import git
from backend.project.maps.map_artifacts import main_project_root

FILE = "DESIGN.md"
MAX_BYTES = 64 * 1024
OBJECT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_CACHE, _LOCK = {}, threading.Lock()  # blob id → (sha256, bytes, markdown, truncated); blob je neměnný


def unavailable(reason):
    return {"available": False, "reason": reason, "file": FILE}


def _root(service, project):
    try:
        return main_project_root(service, project)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def _blob(root):
    """(revize HEAD, blob DESIGN.md) nebo None, jen dva levné `rev-parse` bez čtení obsahu."""
    revision = git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", timeout=5, optional=True)
    if not isinstance(revision, str) or not OBJECT.fullmatch(revision):
        return None, None
    blob = git(root, "rev-parse", "--verify", "--quiet", f"{revision}:{FILE}", timeout=5, optional=True)
    if not isinstance(blob, str) or not OBJECT.fullmatch(blob):
        return revision, None
    if git(root, "cat-file", "-t", blob, timeout=5, optional=True) != "blob":
        return revision, None
    return revision, blob


def _content(root, blob):
    with _LOCK:
        if blob in _CACHE:
            return _CACHE[blob]
    data = git(root, "cat-file", "blob", blob, timeout=15, optional=True, raw=True)
    if not isinstance(data, bytes):
        return None
    value = (hashlib.sha256(data).hexdigest(), len(data),
             data[:MAX_BYTES].decode("utf-8", errors="ignore"), len(data) > MAX_BYTES)
    with _LOCK:
        if len(_CACHE) > 64:
            _CACHE.clear()
        _CACHE[blob] = value
    return value


def read(service, project, *, markdown=True):
    """`{available, file, revision, blob, sha256, bytes, truncated, markdown?}` nebo `{available: false, reason}`."""
    root = _root(service, project)
    if root is None:
        return unavailable("Projekt nemá dostupný zdrojový repozitář.")
    try:
        revision, blob = _blob(root)
        if revision is None:
            return unavailable("Repozitář projektu nemá commit.")
        if blob is None:
            return {**unavailable(f"{FILE} v commitnuté revizi není."), "revision": revision}
        content = _content(root, blob)
    except (ValueError, OSError, subprocess.SubprocessError):
        return unavailable("Repozitář projektu nejde přečíst.")
    if content is None:
        return unavailable("Repozitář projektu nejde přečíst.")
    sha256, size, text, truncated = content
    result = {"available": True, "file": FILE, "revision": revision, "blob": blob, "sha256": sha256,
              "bytes": size, "truncated": truncated}
    return result | {"markdown": text} if markdown else result


def reference(service, project):
    """Odkaz bez obsahu (pro náhled karty a zadání pro office): revize, otisk, velikost."""
    return read(service, project, markdown=False)
