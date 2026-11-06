"""Editor Linie: řádky a kuličky (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3 `GET /board`).

Kulička = ticket s `work`. Spojnice nese kulička, ze které vede: `follows` k navazující práci (ticket, jehož
předchůdce karty je karta této kuličky, jinak další kulička téhož řádku), `planned` k řádku cíle (jen dokud není
začleněno) a `merged` jen podle `work.merged` (zapisuje jen služba po ověřené Git operaci). Plán se nikdy nevrací
jako `merged`. `realMerges` jsou skutečné merge commity main a develop z gitu a špičky větví z gitu.

Editor ukazuje i skutečný stav: pracovní větev z gitu mladší než main, která má commity před rodičem a nemá řádek, dostane
řádek `git: True` (jen ke čtení, id `git:<větev>`) se špičkou větve jako bodem; kulička vznikne až s ticketem.
"""
import time

from backend.agi_pletor.linie import branches
from backend.agi_pletor.linie import rows as rows_mod
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.graph import gh_prs
from backend.integrations.gitio import git
from database.repositories.tickets import TicketStore

TIMEOUT = 15
PR_CACHE = {"at": 0.0, "value": {}}
PR_TTL = 60  # gh se ptá nejvýš jednou za minutu; editor se překresluje častěji


def _prs(root, lookup):
    if lookup is not gh_prs:
        return lookup(root)
    if time.monotonic() - PR_CACHE["at"] > PR_TTL:
        PR_CACHE.update(at=time.monotonic(), value=lookup(root))
    return PR_CACHE["value"]


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


GIT_TYPE = {"feat": "work", "hotfix": "fix"}  # role větve → typ řádku editoru


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


def _ball(ticket, work, rows, prs):
    allowed = work.get("mergeAllowed")
    tip = work_mod.rev(work["repository"], allowed["target"]) if allowed else None
    shown = work_mod.view(ticket, tip)
    pr = prs.get(work["branch"]) if prs else None
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
            "mergeAllowed": allowed, "blocked": work.get("blocked")}


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


def board(service, project, workspace, root, *, pr_lookup=gh_prs):
    """`{rows, balls, mapping, realMerges}` pro editor; kuličky v pořadí vzniku."""
    found = rows_mod.read(service.root, project)
    with service.reading(project):
        tickets = TicketStore(service.db_for(project), project).list_with_work(workspace)
    prs = _prs(root, pr_lookup)
    balls = [_ball(ticket, ticket["work"], found["rows"], prs) for ticket in tickets]
    _follows(tickets, balls)
    extra, tips = git_rows(root, found["rows"], balls)
    return {"rows": found["rows"] + extra, "balls": balls, "mapping": found["mapping"],
            "realMerges": real_merges(root) + tips}
