"""Čtení gitu pro Linii (kontrakt §5): role větví, rodič (strom ze jména, `tree.py`), hloubka, ahead/behind, rozdíl vůči cíli. Nic nemění.

Git běží přes `integrations.gitio.git` (bez shellu, limit 15 s, bez háčků projektu); selhání je `ValueError`
s českou zprávou. Vrací se jen lokální větve; `origin/main` a `origin/develop` jsou zvlášť jako `remote`.
V jednom požadavku (`gitsnap.scope`) se hlavy berou ze snímku referencí a `summary` se čte jednou.
"""
from backend.agi_pletor.linie import gitsnap, tree
from backend.integrations.gitio import git

TIMEOUT = 15
ROLES = tree.ROLES
role = tree.role


def _sha(root, ref):
    return gitsnap.rev(root, ref)


def _heads(root):
    snap = gitsnap._snap(root)
    if snap is not None:  # for-each-ref řadí podle jména, pořadí hlav je stejné jako dřív
        return {name.removeprefix("refs/heads/"): sha for name, sha in snap["commits"].items()
                if name.startswith("refs/heads/")}
    out = git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)\t%(objectname)", timeout=TIMEOUT)
    return dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)


STATUS = ("status", "--porcelain", "--untracked-files=no")
BRANCH = ("rev-parse", "--abbrev-ref", "HEAD")
HEAD = ("rev-parse", "HEAD")


def _counted(heads):
    """Rodiče větví, vůči kterým se počítá ahead/behind, a jejich jedno for-each-ref."""
    parents = sorted({tree.parent(name, heads) for name in heads} & set(heads))
    atoms = "".join(f"\t%(ahead-behind:{parent})" for parent in parents)
    return parents, ("for-each-ref", "refs/heads", "--format=%(refname:short)" + atoms)


def reads(root):
    """Gity `summary`, které jdou předčíst souběžně (`gitsnap.warm`)."""
    parents, counts = _counted(_heads(root))
    return [counts, STATUS, BRANCH, HEAD] if parents else [STATUS, BRANCH, HEAD]


def _ahead_behind(root, heads):
    """`{rodič: {větev: (ahead, behind)}}` vůči všem rodičům jedním voláním for-each-ref."""
    parents, args = _counted(heads)
    if not parents:
        return {}
    out = gitsnap.read(root, *args, optional=False)
    counts = {parent: {} for parent in parents}
    for line in out.splitlines():
        name, *pairs = line.split("\t")
        for parent, pair in zip(parents, pairs):
            ahead, _, behind = pair.partition(" ")
            if ahead.isdigit() and behind.isdigit():
                counts[parent][name] = (int(ahead), int(behind))
    return counts


def summary(root):
    """`{main:{sha, remote}, develop:{sha, remote}|None, server:{branch, sha, dirty}, branches:[...]}`."""
    kept = gitsnap.SCOPE.get()
    if kept is None:
        return _summary(root)
    key = ("summary", gitsnap._key(root))
    if key not in kept:
        kept[key] = _summary(root)
    return kept[key]


def _summary(root):
    heads = _heads(root)
    parents = {name: tree.parent(name, heads) for name in heads}
    counts = _ahead_behind(root, heads)
    branches = []
    for name, sha in sorted(heads.items()):
        parent = parents[name]
        ahead, behind = counts.get(parent, {}).get(name, (0, 0))
        branches.append({"name": name, "role": role(name), "parent": parent, "depth": tree.depth(name, heads), "sha": sha,
                         "ahead": ahead, "behind": behind})
    status = gitsnap.read(root, *STATUS, optional=False)
    return {
        "main": {"sha": heads.get("main"), "remote": _sha(root, "origin/main")},
        "develop": {"sha": heads["develop"], "remote": _sha(root, "origin/develop")} if "develop" in heads else None,
        "server": {"branch": gitsnap.read(root, *BRANCH, optional=False),
                   "sha": gitsnap.read(root, *HEAD, optional=False), "dirty": bool(status)},
        "branches": branches,
    }


def diff(root, branch, target):
    """Rozdíl, který by přešel z `branch` do `target`: `{commits:[{sha7, title}], stat, files}`."""
    for ref in (branch, target):
        if ref.startswith("-") or not _sha(root, ref):
            raise ValueError(f"Větev {ref} v repozitáři neexistuje.")
    log = git(root, "log", "--abbrev=7", "--format=%h %s", f"{target}..{branch}", timeout=TIMEOUT)
    commits = [{"sha7": sha, "title": title} for sha, _, title in (line.partition(" ") for line in log.splitlines())]
    stat = git(root, "diff", "--stat", f"{target}...{branch}", timeout=TIMEOUT)
    files = git(root, "diff", "--name-only", f"{target}...{branch}", timeout=TIMEOUT)
    return {"commits": commits, "stat": stat, "files": len(files.splitlines())}
