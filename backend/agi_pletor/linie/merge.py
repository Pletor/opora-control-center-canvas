"""Začlenění jako služba (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §5): jediné místo, které slučuje.

Předpoklady se ověří těsně před operací, jinak 409 bez zápisu: přijetí platí pro `headSha == git rev-parse branch`
(`no_acceptance` / `head_moved`), povolení je pro tuto hlavu (`not_allowed`), kontroly pro headSha jsou všechny zelené
(`checks_missing` / `checks_failed`), špička cíle (= origin, ne lokální ref) je ta z povolení (`target_moved`). Merge běží v odpojeném worktree
`<data>/pletor/linie/merge/<ticket>`, push `HEAD:target` do origin; `merged.sha` je z `rev-parse HEAD`, nikdy
z hlášení agenta. Opakované volání je idempotentní; když merge proběhl a zápis ne, dožene se z gitu (`origin/target`).

Merge log (docs/navrhy/2026-11-06-linie-rebrand.md §5a, `merge_log.py`): `started` před gitem, `finished` po ověření.
Stejné `op` (nebo dvojice `headSha → target` s hotovým `ok`) další merge neprovede, jen vrátí záznam; `started` bez
`finished` se jen ověří v gitu a dopíše. Začlenění bez `started` (starší než log) se do logu nedopočítává.
Zápis `started` i `finished` jde i do deníku (`linie.merge.started` / `linie.merge.finished`, `journal.py`).

Squash (docs/navrhy/2026-11-08-linie-zkouska.md §2): `feat/*` a `fix/*` jdou do rodiče jedním commitem
(`merge --squash` + commit: titulek, essence, commity `base..head`, trailer `Opora-Mark`), `mode: "squash"`. Hlava
větve pak v cíli není předkem; výsledek se pozná podle commitu s trailerem kuličky (`_landed`). Ostatní merge commitem.
"""
import shutil
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from backend.agi_pletor.linie import journal, merge_log, tree, work_state
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.work import WorkError
from backend.brain_opora.determinism import ticket_lifecycle
from backend.integrations import gitio

TIMEOUT = 120
LOCK = threading.Lock()  # jedno začlenění naráz: dvě souběžná volání nesmí sloučit dvakrát


def _rev(git, root, ref):
    return git(root, "rev-parse", "--verify", "-q", ref + "^{commit}", optional=True) or None


def _ancestor(git, root, older, newer):
    return git(root, "merge-base", "--is-ancestor", older, newer, optional=True) is not None


def _merge_commit(git, root, head, remote):
    """První merge commit na cestě od hlavy ke špičce cíle (ten, který hlavu začlenil), jinak špička."""
    found = git(root, "rev-list", "--merges", "--ancestry-path", "--reverse", f"{head}..{remote}", optional=True)
    return (found or "").split("\n")[0] or git(root, "rev-parse", remote)


def _landed(git, root, started, remote):
    """SHA výsledku začlenění ve špičce cíle `remote`, jinak None."""
    if not _rev(git, root, remote):
        return None
    if started.get("mode") != "squash":
        head = started["source_sha"]
        return _merge_commit(git, root, head, remote) if _ancestor(git, root, head, remote) else None
    # OP-43F5B0.2: squash hlavu do cíle nepřenese; důkazem je commit na linii cíle s trailerem téže kuličky
    found = git(root, "log", "--first-parent", "-1", "--format=%H", "-F", f"--grep=Opora-Mark: {started['mark']}",
                f"{started['target_sha_before']}..{remote}", optional=True)
    return found or None


def mode_for(branch):
    """`squash` pro `feat/*` a `fix/*`, jinak `merge` (merge commit)."""
    return "squash" if tree.role(branch) in ("feat", "fix") else "merge"


def _message(git, root, ticket, head):
    """Odstavce squash commitu: titulek, essence, commity větve `base..head`, trailer `Opora-Mark` (git ho pozná
    jen jako samostatný poslední odstavec)."""
    work, essence = ticket["work"], ticket["body"]["essence"].strip()
    title = work.get("title") or essence.split("\n")[0][:120]
    listed = git(root, "log", "--reverse", "--format=%h %s", f"{work['baseSha']}..{head}", optional=True) or ""
    return [part for part in (title, essence, listed, f"Opora-Mark: {work['mark']}") if part]


def _record(service, project, ticket_id, merged, now):
    with work_mod.store_for(service, project) as store:
        ticket = store.get(ticket_id)
        if not ticket["work"].get("merged"):
            store.set_work(ticket_id, {**ticket["work"], "merged": merged}, now)
            ticket_lifecycle.follow(store.db, project, store.get(ticket_id))  # verified → closed
        return work_mod.present(service, project, store.get(ticket_id))


def _from_log(service, project, ticket_id, entry, now):
    """Hotový záznam logu: `ok` dožene `work.merged` (bez dalšího merge), neúspěch jen vrátí kuličku."""
    started, finished = entry["started"], entry["finished"]
    if not finished["ok"]:
        return work_mod.get(service, project, ticket_id)
    return _record(service, project, ticket_id, {"sha": finished["result_sha"], "target": started["target"],
                                                 "at": finished["at"], "by": started["by"],
                                                 "mode": started["mode"]}, now)


def _finish(service, project, ticket_id, op, sha, ok, now, by):
    done = merge_log.finish(service.root, project, op, sha, ok, now)
    journal.record(service, project, "linie.merge.finished", by, {"ticket": ticket_id, "op": op, "sha": sha}, ok=ok)
    return done


def _confirm(service, project, ticket_id, entry, now, git):
    """`started` bez `finished`: výsledek se jen ověří v gitu a dopíše, merge se znovu nespouští (§5a)."""
    started = entry["started"]
    root, remote = started["repo"], "origin/" + started["target"]
    git(root, "fetch", "origin", started["target"], timeout=TIMEOUT, optional=True)
    landed = _landed(git, root, started, remote)
    if not landed:
        _finish(service, project, ticket_id, entry["op"], None, False, now, "opora")
        raise WorkError("merge_not_done", 409, f"Operace {entry['op']} v gitu neproběhla; zapsáno jako neúspěch.",
                        "Zavolejte merge znovu (nové op).")
    done = _finish(service, project, ticket_id, entry["op"], landed, True, now, "opora")
    return _from_log(service, project, ticket_id, {**entry, "finished": done}, now)


def _precheck(git, work):
    head, accepted, allowed = work.get("headSha"), work.get("acceptance"), work.get("mergeAllowed")
    if not accepted:
        raise WorkError("no_acceptance", 409, "Bez přijetí člověkem služba nic nezačlení.",
                        "Člověk přijme revizi: POST /work/{ticketId}/accept.")
    tip = _rev(git, work["repository"], work["branch"])
    if not head or accepted["sha"] != head or tip != head:
        raise WorkError("head_moved", 409, f"Hlava větve {work['branch']} ({(tip or '-')[:7]}) není přijatá revize "
                        f"{accepted['sha'][:7]}.", "Člověk přijme aktuální revizi znovu.")
    if not allowed or allowed.get("sourceSha") != head:
        raise WorkError("not_allowed", 409, "Začlenění této revize člověk nepovolil.",
                        "POST /work/{ticketId}/allow-merge {target}.")
    if not work_state.checks_for(work, head):
        raise WorkError("checks_missing", 409, f"Pro {head[:7]} nejsou žádné kontroly.", "Pošlete report s kontrolami.")
    if not work_state.green(work):
        raise WorkError("checks_failed", 409, f"Kontroly pro {head[:7]} nejsou všechny zelené.",
                        "Opravte a pošlete report se zelenými kontrolami.")
    return head, allowed["target"]


def _identity(git, root):
    """Bez nastavené identity podepíše merge commit služba OPORA."""
    return () if git(root, "config", "user.email", optional=True) else ("-c", "user.name=OPORA",
                                                                       "-c", "user.email=opora@localhost")


@contextmanager
def detached(git, root, tree, sha):
    """Dočasný odpojený worktree na `sha` (merge, revert); uklidí se vždy."""
    git(root, "worktree", "prune", optional=True)
    shutil.rmtree(tree, ignore_errors=True)
    try:
        git(root, "worktree", "add", "--detach", str(tree), sha, timeout=TIMEOUT)
        yield tree
    finally:
        git(root, "worktree", "remove", "--force", str(tree), optional=True)
        shutil.rmtree(tree, ignore_errors=True)
        git(root, "worktree", "prune", optional=True)


def _operate(git, root, tree, head, branch, target, target_sha, message=None):
    """Merge v odpojeném worktree a push; `(sha, pushed)`. S `message` (odstavce) squash. Worktree se uklidí vždy."""
    with detached(git, root, tree, target_sha):
        who = _identity(git, root)
        if message:  # OP-43F5B0.1: rodič dostane jeden čistý commit na úkol, ne hromadu oprav z větve
            done = git(tree, "merge", "--squash", head, timeout=TIMEOUT, optional=True) is not None and git(
                tree, *who, "commit", "--allow-empty", *(x for part in message for x in ("-m", part)),
                timeout=TIMEOUT, optional=True) is not None
        else:
            done = git(tree, *who, "merge", "--no-ff", "-m", f"Merge {branch} into {target}", head,
                       timeout=TIMEOUT, optional=True) is not None
        if not done:
            git(tree, "reset", "--hard", optional=True)  # squash nemá MERGE_HEAD, --abort by strom nevrátil
            raise WorkError("merge_conflict", 409, f"{branch} nejde čistě začlenit do {target}.",
                            "Agent sloučí cíl do větve, vyřeší konflikt a pošle nový report.")
        sha = git(tree, "rev-parse", "HEAD")
        pushed = git(tree, "push", "origin", f"HEAD:refs/heads/{target}", timeout=TIMEOUT, optional=True) is not None
        return sha, pushed


def _checked_out(git, root, target):
    return f"branch refs/heads/{target}" in git(root, "worktree", "list", "--porcelain").splitlines()


def _op(op):
    if op is None:
        return None
    try:
        return str(uuid.UUID(op))
    except (TypeError, ValueError, AttributeError):
        raise WorkError("invalid_payload", 422, "op je UUID operace začlenění.") from None


def merge(service, project, ticket_id, now, *, op=None, by="opora", git=gitio.git):
    op = _op(op)
    with LOCK:
        ticket = work_mod.get(service, project, ticket_id)
        work = ticket["work"]
        aim = (work.get("mergeAllowed") or {}).get("target") or work.get("target")
        known = merge_log.find(merge_log.read(service.root, project), op, work.get("headSha"), aim)
        if known and known["started"].get("ticket") != ticket_id:
            if op:
                raise WorkError("op_conflict", 409, f"Operace {op} patří jinému úkolu.", "Pošlete nové op.")
            known = None
        if known:  # stejná operace nebo už začleněná dvojice: žádný další merge, jen záznam (§5a)
            return (_from_log(service, project, ticket_id, known, now) if known["finished"]
                    else _confirm(service, project, ticket_id, known, now, git))
        if work.get("merged"):
            return ticket
        head, target = _precheck(git, work)
        root, remote = work["repository"], f"origin/{target}"
        heads = set((git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)", optional=True) or "").split())
        if not tree.may_merge(work["branch"], target, work.get("baseBranch"), heads):
            raise WorkError("target_not_parent", 409, f"{work['branch']} se začleňuje do rodiče "
                            f"{tree.parent(work['branch'], heads, work.get('baseBranch'))}, ne do {target}.",
                            "Člověk povolí začlenění do rodiče (allow-merge).")
        git(root, "fetch", "origin", target, timeout=TIMEOUT, optional=True)
        target_sha, mode = work["mergeAllowed"]["targetSha"], mode_for(work["branch"])
        started = {"source_sha": head, "target_sha_before": target_sha, "mode": mode, "mark": work.get("mark")}
        landed = _landed(git, root, started, remote)
        if landed:  # merge proběhl, zápis ne: dožene se
            merged = {"sha": landed, "target": target, "at": now, "by": "opora", "mode": mode}
            return _record(service, project, ticket_id, merged, now)
        if (_rev(git, root, remote) or _rev(git, root, target)) != target_sha:
            raise WorkError("target_moved", 409, f"Cíl {target} se od povolení posunul.",
                            "Člověk povolí začlenění znovu (allow-merge).")
        # shortcut: místo oddělení nepřijatých změn jiných úkolů jen kontrola, že báze úkolu je ve špičce cíle (M3).
        if not _ancestor(git, root, work["baseSha"], target_sha):
            raise WorkError("not_allowed", 409, f"Báze úkolu {work['baseSha'][:7]} není ve špičce {target}.",
                            "Větev musí vycházet z cíle; nejdřív začleňte rodiče.")
        workdir = Path(service.root) / "pletor" / "linie" / "merge" / ticket_id
        op = op or str(uuid.uuid4())
        # OP-020DBE.1: started před gitem – pád služby po merge zanechá „neověřeno“, ne tiché nic nebo druhý merge
        merge_log.start(service.root, project, {"op": op, "ticket": ticket_id, "repo": root, **started,
                                                "target": target, "branch": work["branch"], "by": by, "at": now})
        journal.record(service, project, "linie.merge.started", by, {"ticket": ticket_id, "op": op, "sha": head},
                       target=target)
        try:
            message = _message(git, root, ticket, head) if mode == "squash" else None
            sha, pushed = _operate(git, root, workdir, head, work["branch"], target, target_sha, message)
            if not pushed:
                git(root, "fetch", "origin", target, timeout=TIMEOUT, optional=True)
                sha = _landed(git, root, started, remote)
                if not sha:
                    raise WorkError("push_failed", 409, f"Push do origin/{target} selhal; nic se nezapsalo.",
                                    "Ověřte přístup k origin a zavolejte merge znovu.")
        except WorkError:  # konflikt i neúspěšný push jsou v gitu ověřený neúspěch
            _finish(service, project, ticket_id, op, None, False, now, by)
            raise
        _finish(service, project, ticket_id, op, sha, True, now, by)
        if not _checked_out(git, root, target):  # lokální ref cíle jen když ho nedrží žádný strom
            git(root, "update-ref", f"refs/heads/{target}", sha, target_sha, optional=True)
        return _record(service, project, ticket_id, {"sha": sha, "target": target, "at": now, "by": by,
                                                     "mode": mode}, now)
