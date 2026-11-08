"""Rychlé čtení gitu pro GET Linie (`/board`, `/graph`): bez subprocesu, dokud se reference nepohnou.

Na Windows stojí každé spuštění gitu desítky ms a board jich dřív dělal stovky. Proto:
- `state(root)` je otisk referencí bez subprocesu: stat `HEAD`, `packed-refs`, souborů pod `refs/` a HEAD všech
  worktree. Commit, report, merge i fetch přepíší některý z nich, takže otisk se změní.
- `scope()` drží po dobu požadavku snímek referencí; jeden snímek na repozitář žije v paměti procesu, dokud se
  otisk nezmění (pak jeden `for-each-ref`). `rev` z něj čte jména větví a origin, `ancestor` a `range_tip`
  počítají předky v Pythonu z mapy rodičů (`log --all`, jednou na snímek).
- `frozen` pamatuje výstup gitu jen pro argumenty z plných SHA: fakta o commitech se nemění, nový commit mění klíč.
- `cached` drží hotovou odpověď, dokud se nezmění její klíč (otisky gitu a stat datových souborů).
Co snímek nezná (tag, zkrácené SHA, smazaný commit), jde do gitu jako dřív; mimo `scope()` se vždy ptá git.
"""
import contextvars
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from backend.integrations.gitio import git

TIMEOUT = 15
SHA = re.compile(r"[0-9a-f]{40}")
PLAIN = re.compile(r"(?!.*\.\.)[A-Za-z0-9._/-]+")  # jméno reference bez ^~:@ a rozsahů
SCOPE = contextvars.ContextVar("linie_gitsnap", default=None)
FROZEN = {}  # (repozitář, argumenty z plných SHA) → výstup gitu
SNAPS = {}  # repozitář → jediný snímek referencí s otiskem `state`; starý se přepíše
GRAPHS = {}  # repozitář → (otisk referencí, {sha: rodiče}, {sha: množina předků}); jen poslední
LIMIT = 2_000  # shortcut: přeplněná paměť se zahodí celá; LRU až kdyby to bylo vidět v profilu
MAX_AGE = 60  # s; hotová odpověď se i beze změny přepočítá (stáří zdrojů, živost relací, špinavý strom)


def _key(root):
    return os.path.normcase(os.path.normpath(str(root)))


@contextmanager
def scope():
    """Snímek na dobu požadavku; vnořený `scope()` použije vnější."""
    if SCOPE.get() is not None:
        yield
        return
    token = SCOPE.set({})
    try:
        yield
    finally:
        SCOPE.reset(token)


def _stat(path):
    try:
        found = os.stat(path)
        return found.st_mtime_ns, found.st_size
    except OSError:
        return None


def files(*paths):
    """Stat souborů (mtime, velikost) jako část klíče; chybějící soubor = None."""
    return tuple((str(path), _stat(path)) for path in paths)


def folder(path):
    """Stat všech souborů jedné složky (bez podsložek)."""
    try:
        with os.scandir(path) as entries:
            return tuple(sorted((e.name, e.stat().st_mtime_ns, e.stat().st_size) for e in entries if e.is_file()))
    except OSError:
        return None


def _gitdirs(root):
    """(gitdir, commondir) repozitáře nebo worktree ze souborů `.git`, bez subprocesu."""
    dot = Path(root) / ".git"
    if dot.is_dir():
        return dot, dot
    own = Path(dot.read_text(encoding="utf-8").split(":", 1)[1].strip())
    own = own if own.is_absolute() else Path(root) / own
    common = own / "commondir"
    return own, ((own / common.read_text(encoding="utf-8").strip()) if common.exists() else own)


def state(root):
    """Otisk referencí bez subprocesu; None = nejde určit (pak se snímek čte vždy znovu).

    Git mění referenci zápisem nového souboru (zámek + přejmenování), takže se změní mtime nebo velikost některého
    souboru pod `refs/`, `packed-refs` nebo HEAD worktree."""
    try:
        own, common = _gitdirs(root)
    except (OSError, IndexError):
        return None
    found = [files(own / "HEAD", common / "HEAD", common / "packed-refs")]
    for top, _, names in os.walk(common / "refs"):
        found.append((top, folder(top)))
    worktrees = common / "worktrees"
    if worktrees.is_dir():
        found.append(tuple(sorted((entry.name, _stat(Path(entry.path) / "HEAD")) for entry in os.scandir(worktrees))))
    return tuple(found)


def cached(store, ident, key, build):
    """Hotová odpověď `build()` pro `ident`, dokud se `key` nezmění a není starší než `MAX_AGE`; jedna na `ident`.
    Klíč se čte před sestavením, takže změna během sestavení vyvolá další přepočet, nikdy starý výsledek."""
    kept = store.get(ident)
    if kept and kept[0] == key and time.monotonic() - kept[1] < MAX_AGE:
        return kept[2]
    at = time.monotonic()
    value = build()
    store[ident] = (key, at, value)
    return value


def _snap(root):
    """`{print, names, commits}` referencí repozitáře v tomto požadavku, mimo `scope()` None. Snímek z paměti
    procesu platí, dokud se nezmění `state`; jinak jeden `for-each-ref`."""
    found = SCOPE.get()
    if found is None:
        return None
    key = _key(root)
    if key not in found:
        mark = state(root)  # otisk před čtením: změna během čtení vyvolá nové čtení příště
        kept = SNAPS.get(key)
        if kept is not None and mark is not None and kept["state"] == mark:
            found[key] = kept
            return kept
        out = git(root, "for-each-ref", "--format=%(refname)%1f%(objecttype)%1f%(objectname)", timeout=TIMEOUT,
                  optional=True)
        if out is None:
            found[key] = None
        else:
            rows = [line.split("\x1f") for line in out.splitlines()]
            found[key] = SNAPS[key] = {"print": out, "names": {name for name, _, _ in rows}, "state": mark,
                                       "commits": {name: sha for name, kind, sha in rows if kind == "commit"}}
    return found[key]


ALL = ("log", "--all", "--format=%H %P")  # mapa rodičů celého repozitáře (~1000 commitů = desítky ms)


def parents_reads(root):
    """`[ALL]`, když mapa rodičů neodpovídá snímku (pro `warm` souběžně s ostatními gity), jinak `[]`."""
    snap, kept = _snap(root), GRAPHS.get(_key(root))
    return [ALL] if snap and (kept is None or kept[0] != snap["print"]) else []


def _graph(root, snap):
    key = _key(root)
    kept = GRAPHS.get(key)
    if kept is None or kept[0] != snap["print"]:
        out = read(root, *ALL) or ""
        kept = GRAPHS[key] = (snap["print"], {sha: rest for sha, _, rest in (l.partition(" ") for l in out.splitlines())}, {})
    return kept


def _ancestors(kept, sha):
    """Množina předků `sha` včetně něj (mapa je uzavřená na předky: obsahuje-li commit, obsahuje i jeho předky)."""
    _, parents, memo = kept
    if sha not in memo:
        seen, stack = set(), [sha]
        while stack:
            item = stack.pop()
            if item in seen:
                continue
            if item in memo:
                seen |= memo[item]
                continue
            seen.add(item)
            stack.extend(parents.get(item, "").split())
        memo[sha] = seen
    return memo[sha]


ASK = object()  # snímek neví, rozhodne git


def _known(root, ref):
    """Plné SHA ze snímku, None = taková reference není, `ASK` = zeptej se gitu."""
    snap = _snap(root)
    if snap is None or not isinstance(ref, str) or not ref:
        return ASK
    if SHA.fullmatch(ref):
        return ref if ref in _graph(root, snap)[1] else ASK
    if not PLAIN.fullmatch(ref) or ref.upper() == ref or re.fullmatch(r"[0-9a-f]{4,39}", ref):
        return ASK  # HEAD, ORIG_HEAD…, zkrácené SHA a výrazy zná jen git
    for name in (ref, "refs/" + ref, "refs/tags/" + ref, "refs/heads/" + ref, "refs/remotes/" + ref,
                 "refs/remotes/" + ref + "/HEAD"):  # pořadí, v jakém jméno rozvádí git (gitrevisions)
        if name in snap["names"]:
            return snap["commits"].get(name, ASK)  # anotovaný tag rozbalí git
    return None


def rev(root, ref):
    """Plné SHA commitu `ref`, nebo None (`rev-parse --verify -q ref^{commit}`)."""
    found = _known(root, ref)
    if found is not ASK:
        return found
    return git(root, "rev-parse", "--verify", "-q", ref + "^{commit}", timeout=TIMEOUT, optional=True) or None


def _in_graph(root, *shas):
    snap = _snap(root)
    kept = _graph(root, snap) if snap else None
    return kept if kept and all(sha in kept[1] for sha in shas) else None


def ancestor(root, older, newer):
    """`merge-base --is-ancestor older newer`: True, když `older` je předkem `newer` (nebo jím je)."""
    a, b = _known(root, older), _known(root, newer)
    if a is None or b is None:
        return False  # neexistující reference: git skončí chybou = False
    kept = None if ASK in (a, b) else _in_graph(root, a, b)
    if kept is None:
        return git(root, "merge-base", "--is-ancestor", older, newer, timeout=TIMEOUT, optional=True) is not None
    return a in _ancestors(kept, b)


def range_tip(root, base, branch):
    """`rev-list -1 base..branch`: špička větve, pokud ji `base` neobsahuje, jinak None. Procházka začíná špičkou,
    takže první vypsaný commit je špička vždy, když sama není předkem `base`."""
    a, b = _known(root, base), _known(root, branch)
    if a is None or b is None:
        return None
    kept = None if ASK in (a, b) else _in_graph(root, a, b)
    if kept is None:
        return git(root, "rev-list", "-1", f"{base}..{branch}", timeout=TIMEOUT, optional=True) or None
    return None if b in _ancestors(kept, a) else b


def read(root, *args, optional=True):
    """`git(root, *args)` jednou na požadavek; výsledek předčtený `warm` se počká. Mimo `scope()` obyčejné volání."""
    kept = SCOPE.get()
    if kept is None:
        return git(root, *args, timeout=TIMEOUT, optional=optional)
    key = ("read", _key(root), args)
    if key not in kept:
        kept[key] = git(root, *args, timeout=TIMEOUT, optional=True)
    out = kept[key]
    out = out.result() if hasattr(out, "result") else out
    if out is None and not optional:
        raise ValueError("Git operace selhala. Ověřte přístup, čistotu pracovního stromu a dostupnost zdroje.")
    return out


def warm(root, calls):
    """Spustí `read` volání souběžně na pozadí (každý git na Windows čeká hlavně na start procesu)."""
    kept = SCOPE.get()
    todo = [args for args in dict.fromkeys(calls) if kept is not None and ("read", _key(root), args) not in kept]
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=len(todo))
    for args in todo:
        kept[("read", _key(root), args)] = pool.submit(git, root, *args, timeout=TIMEOUT, optional=True)
    pool.shutdown(wait=False)


def _pure(args):
    """Za podpříkazem jen přepínače, čísla a plná SHA (i `a..b`, `a^@`): výstup se nemůže změnit."""
    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        parts = arg.removesuffix("^@").split("..")
        if not all(SHA.fullmatch(part) or part.isdigit() for part in parts):
            return False
    return True


def frozen(root, *args, optional=True):
    """`git(root, *args)` s pamětí, když argumenty tvoří jen plná SHA; jinak obyčejné volání. Selhání se nepamatuje."""
    if not _pure(args):
        return git(root, *args, timeout=TIMEOUT, optional=optional)
    key = (_key(root), args)
    if key not in FROZEN:
        out = git(root, *args, timeout=TIMEOUT, optional=optional)
        if out is None:
            return None
        if len(FROZEN) > LIMIT:
            FROZEN.clear()
        FROZEN[key] = out
    return FROZEN[key]


def prefetch(root, calls):
    """Souběžně předčte `frozen` volání, která v paměti nejsou (studený start); výsledek si volající vezme z `frozen`."""
    todo = list({args for args in calls if _pure(args) and (_key(root), args) not in FROZEN})
    if todo:
        with ThreadPoolExecutor(max_workers=min(8, len(todo))) as pool:
            list(pool.map(lambda args: frozen(root, *args), todo))
