"""Budoucnost karty (F4, docs/navrhy/2026-11-11-platno-3-folie.md „F4: kontrakt budoucnosti“): co udělá sloučení
její otevřené práce. Bez modelu a bez testů sousedů, jen git a vazby plátna.

Otevřená práce = úkol Linie karty s větví a cílem (`baseBranch`), dosud nesloučený. Pro každý: `changed`
(`diff cíl...hlava`), `conflicts` (`merge-tree --write-tree`, nečistý strom), `impacts` (sousedé přes vazby obou směrů
a karty se zrcadlem F1 v paměti, jen se společnými soubory zrcadla nebo otevřené práce souseda) a `overlaps` (jiné otevřené úkoly se stejnými soubory).
Git se ptá jen při nové dvojici hlav (`PAIRS` klíčem `(cíl, hlava)`); hlavy čte snímek referencí `gitsnap`.
"""
import os

from backend.agi_pletor.linie import gitsnap
from backend.canvas import plan_reality
from backend.integrations.gitio import git

PLAIN = ("-c", "core.quotePath=false")  # cesty s diakritikou bez oktalových escapů
PAIRS = {}  # (repozitář, druh, targetSha, headSha) → seznam souborů
VERDICTS = {}  # (repozitář, karta) → (podpis otevřené práce, výsledek) pro tečku B a agent-state


def _key(root):
    return os.path.normcase(os.path.normpath(str(root)))


def open_works(works):
    """Nesloučené a Linií neblokované úkoly s větví a cílem."""
    return [work for work in works or [] if work.get("branch") and work.get("baseBranch")
            and not work.get("merged") and not work.get("blocked")]


def repo_of(work, root):
    """Repozitář práce úkolu: větve Linie žijí v `work.repository`, ne nutně v kořeni prostoru."""
    return work.get("repository") or root


def _sign(works):
    return tuple((w.get("repository"), w.get("mark"), w["branch"], w["baseBranch"], w.get("headSha"))
                 for w in open_works(works))


def _files(root, kind, target, head):
    """`changed` nebo `conflicts` dvojice hlav; None = git selhal (nepamatuje se)."""
    key = (_key(root), kind, target, head)
    if key not in PAIRS:
        if kind == "changed":
            out = git(root, *PLAIN, "diff", "--name-only", f"{target}...{head}", timeout=gitsnap.TIMEOUT, optional=True)
        else:
            # OP-11EC95.1: merge-tree je jediný objektivní blok; kód 1 = konflikt, za OID stromu soubory v konfliktu.
            out = git(root, *PLAIN, "merge-tree", "--write-tree", "--name-only", "--no-messages", target, head,
                      timeout=gitsnap.TIMEOUT, optional=True, codes=(0, 1))
            out = None if out is None else "\n".join(out.split("\n\n")[0].splitlines()[1:])
        if out is None:
            return None
        PAIRS[key] = list(dict.fromkeys(line for line in out.splitlines() if line))
    return PAIRS[key]


def _diffs(root, works):
    """`[(karta, práce, cíl, hlava, changed)]` všech otevřených úkolů, které git zná."""
    found = []
    for card, items in works.items():
        for work in open_works(items):
            repo = repo_of(work, root)
            if not os.path.isdir(repo):
                continue  # repozitář úkolu tu není: práce se přeskočí
            target, head = gitsnap.rev(repo, work["baseBranch"]), gitsnap.rev(repo, work["branch"])
            changed = _files(repo, "changed", target, head) if target and head else None
            if changed is not None:
                found.append((card, work, target, head, changed))
    return found


def _code(root, node):
    """Soubory, které podle zrcadla v paměti (F1) mění ostatní karty: `{karta: {cesty}}`."""
    return {other: {item["path"] for key in ("matched", "extra", "symbols") for item in value[key] if item.get("path")}
            for (where, other), (_, value) in list(plan_reality.CARDS.items())  # živá karta ji plní z jiného vlákna
            if where == str(root) and other != node and value}


def card(root, node, nodes, edges, works):
    """`{verdict, works}` karty, nebo None (bez otevřené práce, kterou git zná). `works` = práce úkolů po kartách."""
    if not open_works(works.get(node)):
        return None
    with gitsnap.scope():
        diffs = _diffs(root, works)
        own = [entry for entry in diffs if entry[0] == node]
        conflicts = {id(work): _files(repo_of(work, root), "conflicts", target, head) or []
                     for _, work, target, head, _ in own}
    if not own:
        return None
    names = {item["id"]: item.get("name") or item["id"] for item in nodes}
    related = {}
    for edge in edges:
        if node in (edge["source"], edge["target"]):
            related.setdefault(edge["target"] if edge["source"] == node else edge["source"], edge.get("relation") or "vazba")
    code = _code(root, node)
    result = []
    for _, work, _, _, changed in own:
        mine, here = set(changed), _key(repo_of(work, root))
        same = [entry for entry in diffs if _key(repo_of(entry[1], root)) == here]  # cesty jiného repa nesrovnatelné
        # Soubory souseda = jeho zrcadlo v paměti a jeho vlastní otevřená práce; dopad je jen se společnými soubory.
        touched = {other: set(paths) for other, paths in code.items()}
        for card_id, _, _, _, files in same:
            if card_id != node:
                touched[card_id] = touched.get(card_id, set()) | set(files)
        shared = {other: sorted(touched.get(other, set()) & mine) for other in dict.fromkeys([*related, *touched])}
        impacts = [{"nodeId": other, "name": names.get(other, other), "via": related.get(other, "shares_code"),
                    "paths": paths} for other, paths in shared.items() if other != node and paths]
        overlaps = [{"nodeId": card_id, "mark": other.get("mark"), "branch": other["branch"],
                     "paths": sorted(mine & set(files))}
                    for card_id, other, _, _, files in same if other is not work and mine & set(files)]
        result.append({"mark": work.get("mark"), "branch": work["branch"], "target": work["baseBranch"],
                       "changed": changed, "conflicts": conflicts[id(work)], "impacts": impacts, "overlaps": overlaps})
    verdict = ("blocked" if any(item["conflicts"] for item in result)
               else "warning" if any(item["impacts"] or item["overlaps"] for item in result) else "clean")
    value = {"verdict": verdict, "works": result}
    VERDICTS[(_key(root), node)] = (_sign(works.get(node)), value)
    return value


def remembered(root, node, works):
    """Poslední výsledek karty z paměti, dokud se nezmění její otevřená práce; jinak None (žádný git).
    shortcut: posun cílové větve bez nového hlášení výsledek nezmění, dokud kartu nepřepočítá živá karta nebo hlídač."""
    kept = VERDICTS.get((_key(root), node)) if root else None
    return kept[1] if kept and kept[0] == _sign(works) and kept[0] else None
