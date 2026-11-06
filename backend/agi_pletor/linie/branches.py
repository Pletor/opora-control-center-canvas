"""Čtení gitu pro Linii (kontrakt §5): role větví, rodič, ahead/behind, rozdíl vůči cíli. Nic nemění.

Git běží přes `integrations.gitio.git` (bez shellu, limit 15 s, bez háčků projektu); selhání je `ValueError`
s českou zprávou. Vrací se jen lokální větve; `origin/main` a `origin/develop` jsou zvlášť jako `remote`.
"""
from backend.integrations.gitio import git

TIMEOUT = 15
ROLES = ("topic", "feat", "experiment", "fix", "hotfix")


def role(name):
    """Role z předpony: main, develop, topic, feat, experiment, fix, hotfix, jinak other."""
    if name in ("main", "develop"):
        return name
    prefix = name.split("/", 1)[0]
    return prefix if "/" in name and prefix in ROLES else "other"


def _sha(root, ref):
    return git(root, "rev-parse", "--verify", "-q", ref + "^{commit}", timeout=TIMEOUT, optional=True) or None


def _is_ancestor(root, older, newer):
    return git(root, "merge-base", "--is-ancestor", older, newer, timeout=TIMEOUT, optional=True) is not None


def _parent(root, name, heads):
    kind = role(name)
    if kind == "main":
        return None
    if kind in ("develop", "hotfix"):
        return "main"
    base = "develop" if "develop" in heads else "main"
    if kind in ("topic", "experiment"):
        return base
    # shortcut: rodič je první topic/*, jehož HEAD je předek větve (ne nejbližší podle merge-base);
    # stačí, dokud téma nemá víc vnořených topic větví.
    for topic in heads:
        if role(topic) == "topic" and topic != name and _is_ancestor(root, heads[topic], heads[name]):
            return topic
    return base


def _heads(root):
    out = git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)\t%(objectname)", timeout=TIMEOUT)
    return dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)


def _ahead_behind(root, parent):
    """`{větev: (ahead, behind)}` vůči rodiči jedním voláním for-each-ref."""
    out = git(root, "for-each-ref", "refs/heads", f"--format=%(refname:short)\t%(ahead-behind:{parent})",
              timeout=TIMEOUT)
    counts = {}
    for line in out.splitlines():
        name, _, pair = line.partition("\t")
        ahead, _, behind = pair.partition(" ")
        if ahead.isdigit() and behind.isdigit():
            counts[name] = (int(ahead), int(behind))
    return counts


def summary(root):
    """`{main:{sha, remote}, develop:{sha, remote}|None, server:{branch, sha, dirty}, branches:[...]}`."""
    heads = _heads(root)
    parents = {name: _parent(root, name, heads) for name in heads}
    counts = {parent: _ahead_behind(root, parent) for parent in set(parents.values()) if parent}
    branches = []
    for name, sha in sorted(heads.items()):
        parent = parents[name]
        ahead, behind = counts.get(parent, {}).get(name, (0, 0))
        branches.append({"name": name, "role": role(name), "parent": parent, "sha": sha,
                         "ahead": ahead, "behind": behind})
    status = git(root, "status", "--porcelain", "--untracked-files=no", timeout=TIMEOUT)
    return {
        "main": {"sha": heads.get("main"), "remote": _sha(root, "origin/main")},
        "develop": {"sha": heads["develop"], "remote": _sha(root, "origin/develop")} if "develop" in heads else None,
        "server": {"branch": git(root, "rev-parse", "--abbrev-ref", "HEAD", timeout=TIMEOUT),
                   "sha": git(root, "rev-parse", "HEAD", timeout=TIMEOUT), "dirty": bool(status)},
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
