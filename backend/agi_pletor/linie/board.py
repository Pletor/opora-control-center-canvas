"""Editor Linie: řádky a kuličky (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3 `GET /board`).

Kulička = ticket s `work`. Spojnice nese kulička, ze které vede: `follows` k navazující práci (ticket, jehož
předchůdce karty je karta této kuličky, jinak další kulička téhož řádku), `planned` k řádku cíle (jen dokud není
začleněno) a `merged` jen podle `work.merged` (zapisuje jen služba po ověřené Git operaci). Plán se nikdy nevrací
jako `merged`. `realMerges` jsou skutečné merge commity main a develop z gitu a špičky větví z gitu.

Řádek editoru je větev (`with_tree`, kontrakt „Řádek = větev“): kulička leží na řádku své větve.

Editor ukazuje i skutečný stav: pracovní větev z gitu mladší než main, která má commity před rodičem a nemá řádek, dostane
řádek `git: True` (jen ke čtení, id `git:<větev>`) se špičkou větve jako bodem; kulička vznikne až s ticketem.
"""
import time
import uuid

from backend.agi_pletor.linie import branches, tree
from backend.agi_pletor.linie import rows as rows_mod
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.graph import gh_prs
from backend.brain_opora.determinism import tokens
from backend.integrations.gitio import git
from database.repositories.tickets import TicketStore

TIMEOUT = 15
PR_CACHE = {"at": 0.0, "value": {}, "good": {}, "source": {"verifiedAt": None, "lastSuccessAt": None, "ok": False}}
PR_TTL = 60  # gh se ptá nejvýš jednou za minutu; editor se překresluje častěji


def _read_prs(root, lookup, good):
    """`(prs, source)`; při selhání zůstanou poslední známé PR (stav beze změny, `unconfirmed: True`) a zdroj nese
    `lastSuccessAt` (poslední úspěšné čtení, = `verifiedAt`) odděleně od `attemptedAt` (poslední pokus)."""
    attempted = tokens.stamp()
    try:
        found = lookup(root)
    except Exception:  # noqa: BLE001 – jakékoli selhání poskytovatele PR = „nevím“, ne pád boardu
        found = None
    # shortcut: gh_prs maskuje selhání jako {} (graph.py mimo scope L7a); pro gh je prázdný výsledek selhání.
    if found is None or (lookup is gh_prs and not found):
        return ({branch: {**pr, "unconfirmed": True} for branch, pr in good[0].items()},
                {"verifiedAt": good[1], "lastSuccessAt": good[1], "attemptedAt": attempted, "ok": False})
    return found, {"verifiedAt": attempted, "lastSuccessAt": attempted, "attemptedAt": attempted, "ok": True}


def _prs(root, lookup):
    if lookup is not gh_prs:
        return _read_prs(root, lookup, ({}, None))
    if time.monotonic() - PR_CACHE["at"] > PR_TTL:
        value, source = _read_prs(root, lookup, (PR_CACHE["good"], PR_CACHE["source"]["lastSuccessAt"]))
        PR_CACHE.update(at=time.monotonic(), value=value, source=source, **({"good": value} if source["ok"] else {}))
    return PR_CACHE["value"], PR_CACHE["source"]


def _commits(root, work):
    if not work.get("headSha"):
        return 0
    found = git(root, "rev-list", "--count", f"{work['baseSha']}..{work['headSha']}", timeout=TIMEOUT, optional=True)
    return int(found) if found and found.isdigit() else 0


def real_merges(root):
    """Posledních 20 merge commitů na main a develop: `[{target, sha, parents, at, title}]`."""
    found = []
    for target in rows_mod.MAPPING.values():
        out = git(root, "log", "--merges", "-n", "20", "--format=%H%x1f%P%x1f%cI%x1f%s", target, "--",
                  timeout=TIMEOUT, optional=True) or ""
        for line in out.splitlines():
            sha, parents, at, title = line.split("\x1f", 3)
            found.append({"target": target, "sha": sha, "parents": parents.split(), "at": at, "title": title})
    return found


GIT_TYPE = {"feat": "work", "hotfix": "fix"}  # role větve → typ řádku editoru (items, fix, experiment beze změny)


def git_rows(root, rows, balls):
    """Řádky z gitu pro nesloučené pracovní větve bez řádku ani kuličky + jejich špičky jako body `realMerges`."""
    known = {row.get("branch") for row in rows} | {ball["branch"] for ball in balls}
    # shortcut: větev mladší než špička main = rozpracovaná; starší (squashem už v main) by editor jen zaplevelily.
    stamps = git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)	%(committerdate:unix)",
                 timeout=TIMEOUT, optional=True) or ""
    when = {name: int(at) for name, _, at in (line.partition("	") for line in stamps.splitlines()) if at.isdigit()}
    found, tips = [], []
    for order, b in enumerate(branches.summary(root)["branches"]):
        if (b["role"] not in branches.ROLES or b["name"] in known or not b["ahead"]
                or when.get(b["name"], 0) <= when.get("main", 0)):
            continue
        found.append({"id": "git:" + b["name"], "name": b["name"], "type": GIT_TYPE.get(b["role"], b["role"]),
                      "ticketId": None, "branch": b["name"], "base": {"branch": b["parent"], "sha": None},
                      "target": b["parent"], "collapsed": False, "order": 10_000 + order, "git": True,
                      "ahead": b["ahead"]})
        line = git(root, "log", "-1", "--format=%H%x1f%cI%x1f%s", b["name"], "--", timeout=TIMEOUT, optional=True)
        if line:
            sha, at, title = line.split("", 2)
            tips.append({"target": b["name"], "sha": sha, "parents": [], "at": at, "title": title})
    return found, tips


def _row_for(rows, branch):
    return next((row["id"] for row in rows if row.get("branch") == branch), branch)


VIEW = ("axes", "summary", "allowed", "blocked", "incomplete", "evidence")


def _ball(ticket, work, rows, prs, sources):
    allowed = work.get("mergeAllowed")
    pr = prs.get(work["branch"]) if prs else None
    shown = work_mod.view(ticket, sources, pr)
    links = []
    if work.get("merged"):
        links.append({"to": _row_for(rows, work["merged"]["target"]), "kind": "merged", "sha": work["merged"]["sha"]})
    elif work.get("target"):
        links.append({"to": _row_for(rows, work["target"]), "kind": "planned"})
    return {"ticketId": ticket["ticketId"], "rowId": work["rowId"], "mark": work.get("mark"),
            "title": work.get("title") or ticket["body"]["essence"].split("\n")[0][:120],
            "state": shown["state"], "stateLabel": shown["stateLabel"], "next": shown["next"],
            "branch": work["branch"], "headSha7": (work.get("headSha") or "")[:7] or None,
            "createdAt": ticket["createdAt"], "mergedAt": (work.get("merged") or {}).get("at"),
            "counts": {"commits": _commits(work["repository"], work),
                       "prs": None if not prs else int(pr is not None), "merges": int(bool(work.get("merged")))},
            "links": links, "pr": pr, "preview": work.get("preview"), "acceptance": work.get("acceptance"),
            # `blocked` = {akce: důvod} z evaluate (L7 §4); ruční blokace kuličky je `block`.
            "mergeAllowed": allowed, "block": work.get("blocked"), **{key: shown[key] for key in VIEW}}


def _follows(tickets, balls):
    """Spojnice `follows` od předchozí práce: předchůdce karty má přednost před předchozí kuličkou řádku."""
    by_card = {t["machine"]["cardId"]: ball for t, ball in zip(tickets, balls) if t["machine"]["cardId"]}
    last_in_row = {}
    for ticket, ball in zip(tickets, balls):
        cards = [item["cardId"] for item in ticket["machine"]["predecessors"] if item["cardId"] in by_card]
        before = by_card[cards[0]] if cards else last_in_row.get(ball["rowId"])
        if before is not None and before is not ball:
            before["links"].insert(0, {"to": ball["ticketId"], "kind": "follows"})
        last_in_row[ball["rowId"]] = ball


def with_tree(rows, balls, heads):
    """Řádek = větev: jeden řádek na větev ručních řádků, kuliček a gitu, seřazený depth-first podle `tree.order`.

    Ruční řádek drží svou větev (`branch`, jinak větev své první kuličky); větve kuliček bez řádku dostanou
    automatický řádek `auto:<větev>`. Ruční řádky bez větve (nebo s už obsazenou) jdou na konec jako `planned`.
    """
    # Blokovaná kulička na větvi, která už v gitu není, řádek nezakládá: zůstává na svém ručním řádku jako historie.
    live = [ball for ball in balls if not ball.get("block") or ball["branch"] in heads]
    first = {}
    for ball in live:
        first.setdefault(ball["rowId"], ball["branch"])
    header = next((row for row in rows if row.get("id") == "items"), None)  # pevná hlavička Items bez větve
    claimed, leftover = {}, []
    for row in rows:
        if row is header:
            continue
        branch = row.get("branch") or first.get(row["id"])
        if branch and branch not in claimed:
            claimed[branch] = row
        else:
            leftover.append(row)
    known = set(heads) | set(claimed) | {ball["branch"] for ball in live}

    def auto(branch):
        above = tree.parent(branch, known)
        return {"id": "auto:" + branch, "name": branch, "type": "items" if tree.role(branch) == "items" else "work",
                "ticketId": None, "branch": branch, "base": {"branch": above, "sha": None}, "target": above,
                "collapsed": False, "auto": True}

    for ball in live:
        if ball["branch"] not in claimed:
            claimed[ball["branch"]] = auto(ball["branch"])
    # Rodič bez vlastní práce (kořen komponenty, který teprve sbírá děti) dostane řádek, pokud větev v gitu existuje.
    for branch in list(claimed):
        above = tree.parent(branch, known)
        while above and above in heads and above not in claimed and above not in rows_mod.MAPPING:
            claimed[above] = auto(above)
            above = tree.parent(above, known)
    place = {name: index for index, name in enumerate(tree.order(known))}

    def shaped(row, branch, planned):
        above = (row.get("base") or {}).get("branch") or (tree.parent(branch, known) if branch else None)
        deep = tree.depth(branch, known) if branch else tree.depth("develop", known) + 1
        if branch and tree.role(branch) == "items":
            deep += 1  # items/<díl> leží pod hlavičkou Items
        return {**row, "branch": branch, "parent": above, "depth": deep, "baseBranch": above,
                "auto": bool(row.get("auto") or row.get("git")), "planned": planned}

    ordered = sorted(claimed.items(), key=lambda item: place.get(item[0], len(place)))
    found = [shaped(row, branch, False) for branch, row in ordered]
    if header:
        at = next((i for i, row in enumerate(found) if row["branch"] not in rows_mod.MAPPING), len(found))
        found.insert(at, shaped(header, None, False))
    return found + [shaped(row, None, True) for row in sorted(leftover, key=lambda r: r.get("order", 0))]


def board(service, project, workspace, root, *, pr_lookup=gh_prs):
    """`{rows, balls, mapping, realMerges, snapshot}` pro editor; kuličky v pořadí vzniku.

    `snapshot.sources.<zdroj>.verifiedAt` je čas skutečného čtení zdroje v tomto sestavení (PR z cache = čas
    posledního úspěšného čtení), ne čas požadavku; `builtAt` je čas sestavení (L7 §4).
    """
    found = rows_mod.read(service.root, project)
    with service.reading(project):
        tickets = TicketStore(service.db_for(project), project).list_with_work(workspace)
    db_at = tokens.stamp()
    heads = set(branches._heads(root))
    git_at = tokens.stamp()
    prs, pr_source = _prs(root, pr_lookup)
    sources = {"git": {"verifiedAt": git_at, "ok": bool(heads)}, "prs": pr_source,
               "checks": {"verifiedAt": db_at, "ok": True}, "sessions": {"verifiedAt": db_at, "ok": True},
               "deploy": {"verifiedAt": None, "ok": False}}  # nasazení zatím nemá zdroj (L7 §7.3)
    balls = [_ball(ticket, ticket["work"], found["rows"], prs, sources) for ticket in tickets]
    _follows(tickets, balls)
    extra, tips = git_rows(root, found["rows"], balls)
    rows = with_tree(found["rows"] + extra, balls, heads)
    row_of = {row["branch"]: row["id"] for row in rows if not row["planned"]}
    for ball in balls:  # kulička patří řádku své větve; spojnice na větve míří na jejich řádky
        ball["rowId"] = row_of.get(ball["branch"], ball["rowId"])
        for link in ball["links"]:
            if link["kind"] != "follows":
                link["to"] = row_of.get(link["to"], link["to"])
    return {"rows": rows, "balls": balls, "mapping": found["mapping"],
            "realMerges": real_merges(root) + tips,
            "snapshot": {"id": "snap_" + uuid.uuid4().hex[:12], "builtAt": tokens.stamp(), "sources": sources}}
