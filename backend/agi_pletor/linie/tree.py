"""Strom větví Linie (docs/navrhy/2026-11-06-linie-strom-vetvi.md): role, rodič a pořadí ze jména. Čisté, bez gitu.

Pevné větve main, develop, items/*; feat/* se zanořují podle jména (`feat/a-b-c` pod nejdelší existující prefix
na hranici `-`); fix/* a experiment/* nemají rodiče ve jménu, ten nese `base` z práce.
"""
ROLES = ("items", "feat", "experiment", "fix", "hotfix")


def role(name):
    """main, develop, items, feat, experiment, fix, hotfix, jinak other."""
    if name in ("main", "develop"):
        return name
    prefix = name.split("/", 1)[0]
    return prefix if "/" in name and prefix in ROLES else "other"


def _prefixes(name):
    """Prefixy `feat/a-b-c` na hranici `-`, nejdelší první: `feat/a-b`, `feat/a`."""
    head, _, rest = name.partition("/")
    parts = rest.split("-")
    return [f"{head}/{'-'.join(parts[:i])}" for i in range(len(parts) - 1, 0, -1) if parts[0]]


def parent(name, heads, base=None):
    kind = role(name)
    if kind == "main":
        return None
    if kind in ("develop", "hotfix"):
        return "main"
    if kind == "feat":
        return next((p for p in _prefixes(name) if p in heads), "develop")
    if kind in ("fix", "experiment") and base:
        return base
    return "develop"


def is_child(branch, base, heads):
    kind = role(branch)
    if kind == "feat":
        found = _prefixes(branch)
        return base in found or (base == "develop" and not any(p in heads for p in found))
    if kind in ("develop", "hotfix"):
        return base == "main"
    if kind == "items":
        return base == "develop"
    return base in heads or base == "main"


def may_merge(branch, target, base, heads):
    """Cíl začlenění je rodič (nebo báze z práce); `items/*` smí i do develop a feat větve (povolí člověk)."""
    if role(branch) == "items" and (target == "develop" or role(target) == "feat"):
        return True
    return target in (base, parent(branch, heads, base))


def depth(name, heads):
    """main 0, develop 1, items/* a kořen feat 2, každé zanoření o 1 níž."""
    count = 0
    while name != "main" and count < 50:
        name, count = parent(name, heads), count + 1
    return count


def order(heads):
    """Depth-first: main, develop, items/* abecedně, feat stromy (rodič před dětmi), nakonec ostatní."""
    names = set(heads)
    feats = sorted(n for n in names if role(n) == "feat")
    kids = {}
    for name in feats:
        kids.setdefault(parent(name, names), []).append(name)

    def walk(name):
        return [name, *(x for kid in kids.get(name, []) for x in walk(kid))]

    done = [n for n in ("main", "develop") if n in names] + sorted(n for n in names if role(n) == "items")
    done += [x for root in kids.get("develop", []) for x in walk(root)]
    return done + sorted(names - set(done))
