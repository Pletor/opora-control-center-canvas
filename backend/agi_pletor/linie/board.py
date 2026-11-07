"""Editor Linie: řádky a kuličky (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3 `GET /board`).

Kulička = ticket s `work`. Spojnice nese kulička, ze které vede: `follows` k navazující práci (ticket, jehož
předchůdce karty je karta této kuličky, jinak další kulička téhož řádku), `planned` k řádku cíle (jen dokud není
začleněno) a `merged` jen podle `work.merged` (zapisuje jen služba po ověřené Git operaci). Plán se nikdy nevrací
jako `merged`. `realMerges` jsou skutečné merge commity main a develop z gitu a špičky větví z gitu.

Řádek editoru je větev (`with_tree`, kontrakt „Řádek = větev“): kulička leží na řádku své větve.

Editor ukazuje i skutečný stav: pracovní větev z gitu mladší než main, která má commity před rodičem a nemá řádek, dostane
řádek `git: True` (jen ke čtení, id `git:<větev>`) se špičkou větve jako bodem; kulička vznikne až s ticketem.

Skutečná data (docs/navrhy/2026-11-06-linie-rebrand.md §5, §5a, L7c): `tags` z `git for-each-ref refs/tags` (tag patří
commitu, řádek kreslení volí frontend), `worktrees` z `git worktree list --porcelain` (agent a od–do jen s vazbou relace
z `run`), `deploy.envs` z událostí prostředí, PR s posledním známým stavem při výpadku a `commits[]` kuličky s
`abandoned`.

L7d (§7 bod 4): každá kulička nese `plan` (`plan_link`) a `queues`, board `queues` (`plan_view.queues`) nad týmž
grafem prostoru; `grouped(..., "plan", snapshot)` přeskládá uložený snímek podle plánu bez nového čtení.

L7g (§7 bod 7): `queues.human[]` = seřazená fronta „Čeká na tebe“ (`human_queue.order`) nad řádky podle větví.
"""
import os
import time
import uuid
from pathlib import Path

from backend.agi_pletor.linie import (
    branches,
    deploy,
    human_queue,
    jsonfile,
    merge_log,
    plan_link,
    plan_view,
    trace_git,
    tree,
)
from backend.agi_pletor.linie import rows as rows_mod
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.graph import gh_lookup
from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.integrations.gitio import git
from database.repositories.tickets import TicketStore

TIMEOUT = 15
PR_SEEN = {}  # repozitář → (monotonic, prs, source); jen skutečné gh
PR_TTL = 60  # gh se ptá nejvýš jednou za minutu; editor se překresluje častěji


def read_prs(data_root, root, lookup):
    """`(prs, source)`. Úspěšné čtení (i prázdné) se uloží do `<data>/pletor/linie/prs.json`; při výpadku zůstanou
    poslední známé PR (`unconfirmed: True`) a zdroj nese `lastSuccessAt` odděleně od `attemptedAt`."""
    attempted, path, key = tokens.stamp(), Path(data_root) / "pletor" / "linie" / "prs.json", str(root)
    try:
        found = lookup(root)
    except Exception as error:  # noqa: BLE001 – jakékoli selhání poskytovatele PR = „nevím“, ne pád boardu
        found = {"prs": {}, "ok": False, "error": type(error).__name__}
    if found.get("ok"):
        jsonfile.update(path, {}, lambda cache: {**(cache if isinstance(cache, dict) else {}),
                                                 key: {"prs": found["prs"], "lastSuccessAt": attempted}})
        return found["prs"], {"verifiedAt": attempted, "lastSuccessAt": attempted, "attemptedAt": attempted,
                              "ok": True, "error": None}
    cache = jsonfile.read(path, {})
    last = (cache.get(key) if isinstance(cache, dict) else None) or {}
    return ({branch: {**pr, "unconfirmed": True} for branch, pr in (last.get("prs") or {}).items()},
            {"verifiedAt": last.get("lastSuccessAt"), "lastSuccessAt": last.get("lastSuccessAt"),
             "attemptedAt": attempted, "ok": False, "error": found.get("error")})


def _prs(data_root, root, lookup):
    if lookup is not gh_lookup:
        return read_prs(data_root, root, lookup)
    seen = PR_SEEN.get(str(root))
    if not seen or time.monotonic() - seen[0] > PR_TTL:
        seen = PR_SEEN[str(root)] = (time.monotonic(), *read_prs(data_root, root, lookup))
    return seen[1], seen[2]


def _commits(work):
    """Commity větve nad bází (nejstarší první) s rozhodnutím `abandoned` (git ani HEAD nemění)."""
    gave_up = {item["sha"]: {k: item[k] for k in ("why", "at", "by")} for item in work.get("abandoned") or []}
    found = trace_git._log(work["repository"], f"{work['baseSha']}..{work['branch']}") if work.get("headSha") else []
    return [{"sha": c["sha"], "sha7": c["sha7"], "title": c["title"], "at": c["at"], "mark": c["trailers"]["mark"],
             "abandoned": gave_up.get(c["sha"])} for c in reversed(list(found))]


def tags(root):
    """`[{name, sha, at, annotated}]`: lehké i anotované tagy na commit; `sha` je commit (u anotovaných cíl tagu)."""
    out = git(root, "for-each-ref", "refs/tags", "--format=%(refname:short)%1f%(objecttype)%1f%(objectname)%1f"
              "%(*objecttype)%1f%(*objectname)%1f%(creatordate:iso-strict)", timeout=TIMEOUT, optional=True) or ""
    found = []
    for line in out.splitlines():
        name, kind, sha, target_kind, target, at = line.split("\x1f")
        if kind == "commit" or (kind == "tag" and target_kind == "commit"):
            found.append({"name": name, "sha": target if kind == "tag" else sha, "at": at, "annotated": kind == "tag"})
    return found


def _norm(path):
    return os.path.normcase(os.path.normpath(path))


def worktrees(root, tickets):
    """`[{path, branch, sha, binding}]`; `binding` (agent, od–do) jen když relace `run` výslovně uvedla tento worktree."""
    bound = {}
    for ticket in tickets:
        for run in ticket["work"].get("runs") or []:
            key = _norm(run["worktree"]) if run.get("worktree") else None
            if key and (key not in bound or (run.get("heartbeat") or "") > (bound[key][1].get("heartbeat") or "")):
                bound[key] = (ticket["ticketId"], run)
    found = []
    out = git(root, "worktree", "list", "--porcelain", timeout=TIMEOUT, optional=True) or ""
    for block in out.split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines() if line)
        if "worktree" not in fields:
            continue
        ref = fields.get("branch", "")
        ticket_id, run = bound.get(_norm(fields["worktree"]), (None, None))
        alive = bool(run) and work_mod.live(run)
        binding = None if run is None else {
            "ticketId": ticket_id, "attempt": run["runId"], "agent": run.get("agent"), "from": run["startedAt"],
            "to": None if alive else run.get("heartbeat"), "heartbeat": run.get("heartbeat"), "live": alive}
        found.append({"path": fields["worktree"], "branch": ref.removeprefix("refs/heads/") if ref else None,
                      "sha": fields.get("HEAD"), "binding": binding})
    return found


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


VIEW = ("axes", "summary", "allowed", "blocked", "incomplete", "evidence", "plan")


def _ball(service, project, ticket, rows, prs, sources, log, events, by_mark, graph):
    work = ticket["work"]
    allowed = work.get("mergeAllowed")
    commits = _commits(work)
    pr = prs.get(work["branch"]) if prs else None
    if pr is not None:  # PR řeší úkoly podle Opora-Mark svých commitů, jinak úkol své větve
        marked = sorted({by_mark[c["mark"]] for c in commits if c["mark"] in by_mark})
        pr = {**pr, "ticketIds": marked or [ticket["ticketId"]]}
    shown = work_mod.view(ticket, sources, pr, work_mod.facts(service, project, ticket, pr, log, events, graph))
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
            "counts": {"commits": len(commits), "prs": int(pr is not None) if sources["prs"]["ok"] or prs else None,
                       "merges": int(bool(work.get("merged")))},
            "links": links, "pr": pr, "commits": commits, "preview": work.get("preview"), "acceptance": work.get("acceptance"),
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


def board(service, project, workspace, root, *, pr_lookup=gh_lookup):
    """`{rows, balls, mapping, realMerges, tags, worktrees, deploy, snapshot}` pro editor; kuličky v pořadí vzniku.

    `snapshot.sources.<zdroj>.verifiedAt` je čas skutečného čtení zdroje v tomto sestavení (PR z cache = čas
    posledního úspěšného čtení, `deploy` = přečtení záznamu událostí; stáří události je v `envs[env].at`), ne čas
    požadavku; `builtAt` je čas sestavení (L7 §4).
    """
    found = rows_mod.read(service.root, project)
    with service.reading(project):
        store = TicketStore(service.db_for(project), project)
        tickets = store.list_with_work(workspace)
        # shortcut: všechny tickety prostoru do 100 000; fronta plánů nad větším projektem až s dotazem na card_id.
        carded = {t["machine"]["cardId"] for t in store.list(workspace, limit=100_000) if t["machine"]["cardId"]}
        graph = plan_link.cards(service, project, workspace)
    db_at = tokens.stamp()
    heads = set(branches._heads(root))
    git_at = tokens.stamp()
    prs, pr_source = _prs(service.root, root, pr_lookup)
    log, events = merge_log.read(service.root, project), deploy.read(service.root, project)
    deploy_at = tokens.stamp()  # čas přečtení záznamu událostí; stáří události nese axes.deploy.envs[env].at
    shipped = [e for e in events if _norm(e.get("repo") or "") == _norm(str(root))]
    sources = {"git": {"verifiedAt": git_at, "ok": bool(heads)}, "prs": pr_source,
               "checks": {"verifiedAt": db_at, "ok": True}, "sessions": {"verifiedAt": db_at, "ok": True},
               "deploy": {"verifiedAt": deploy_at, "ok": True}}
    by_mark = {t["work"].get("mark"): t["ticketId"] for t in tickets if t["work"].get("mark")}
    with service.reading(project):  # jeden snímek grafu pro revize karet všech kuliček
        balls = [_ball(service, project, ticket, found["rows"], prs, sources, log, events, by_mark, graph)
                 for ticket in tickets]
    plan_link.settle([ball["plan"] for ball in balls])
    for ball in balls:
        ball["queues"] = plan_view.ball_queues(ball)
    _follows(tickets, balls)
    extra, tips = git_rows(root, found["rows"], balls)
    rows = with_tree(found["rows"] + extra, balls, heads)
    row_of = {row["branch"]: row["id"] for row in rows if not row["planned"]}
    for ball in balls:  # kulička patří řádku své větve; spojnice na větve míří na jejich řádky
        ball["rowId"] = row_of.get(ball["branch"], ball["rowId"])
        for link in ball["links"]:
            if link["kind"] != "follows":
                link["to"] = row_of.get(link["to"], link["to"])
    human = human_queue.order(balls, rows)
    result = {"rows": rows, "balls": balls, "mapping": found["mapping"], "group": "branch",
              "realMerges": real_merges(root) + tips, "tags": tags(root), "worktrees": worktrees(root, tickets),
              "deploy": {"envs": deploy.latest(shipped)},
              "queues": {**plan_view.queues(balls, graph, carded), "humanDecisions": len(human), "human": human},  # jeden zdroj pravdy
              "snapshot": {"id": "snap_" + uuid.uuid4().hex[:12], "builtAt": tokens.stamp(), "sources": sources}}
    plan_view.remember(project, workspace, result, graph)
    return result


def grouped(service, project, workspace, root, group="branch", snapshot=None, *, pr_lookup=gh_lookup):
    """`GET /board?group&snapshot`: `group=plan` přeskládá týž snímek (`snapshot` z paměti, bez čtení gitu, L7d);
    bez `snapshot` se board sestaví znovu. Neznámý snímek = 404 `snapshot_not_found`."""
    if group not in ("branch", "plan"):
        raise GateError(422, "invalid_payload", "group je branch nebo plan.", "Například ?group=plan.")
    kept = plan_view.recall(project, workspace, snapshot) if snapshot else None
    if snapshot and kept is None:
        raise GateError(404, "snapshot_not_found", "Snímek boardu už v paměti není.", "Načtěte GET /board znovu.")
    if kept is None:
        built = board(service, project, workspace, root, pr_lookup=pr_lookup)
        kept = plan_view.recall(project, workspace, built["snapshot"]["id"])
    found, names = kept
    return plan_view.group(found, names) if group == "plan" else found
