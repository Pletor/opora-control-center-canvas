"""Začlenění jako služba (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §5): jediné místo, které slučuje.

Předpoklady se ověří těsně před operací, jinak 409 bez zápisu: přijetí platí pro `headSha == git rev-parse branch`
(`no_acceptance` / `head_moved`), povolení je pro tuto hlavu (`not_allowed`), kontroly pro headSha jsou všechny zelené
(`checks_missing` / `checks_failed`), špička cíle je ta z povolení (`target_moved`). Merge běží v odpojeném worktree
`<data>/pletor/linie/merge/<ticket>`, push `HEAD:target` do origin; `merged.sha` je z `rev-parse HEAD`, nikdy
z hlášení agenta. Opakované volání je idempotentní; když merge proběhl a zápis ne, dožene se z gitu (`origin/target`).
"""
import shutil
import threading
from pathlib import Path

from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie import work_state
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


def _record(service, project, ticket_id, merged, now):
    with work_mod.store_for(service, project) as store:
        ticket = store.get(ticket_id)
        if not ticket["work"].get("merged"):
            store.set_work(ticket_id, {**ticket["work"], "merged": merged}, now)
            ticket_lifecycle.follow(store.db, project, store.get(ticket_id))  # verified → closed
        return work_mod.view(store.get(ticket_id))


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


def _operate(git, root, tree, head, branch, target, target_sha):
    """Merge v odpojeném worktree a push; `(sha, pushed)`. Worktree se uklidí vždy."""
    git(root, "worktree", "prune", optional=True)
    shutil.rmtree(tree, ignore_errors=True)
    try:
        git(root, "worktree", "add", "--detach", str(tree), target_sha, timeout=TIMEOUT)
        # shortcut: i feat/* a fix/* do rodiče jdou merge commitem (--no-ff); squash podle typu řádku až po M3.
        if git(tree, *_identity(git, root), "merge", "--no-ff", "-m", f"Merge {branch} into {target}", head,
               timeout=TIMEOUT, optional=True) is None:
            git(tree, "merge", "--abort", optional=True)
            raise WorkError("merge_conflict", 409, f"{branch} nejde čistě začlenit do {target}.",
                            "Agent sloučí cíl do větve, vyřeší konflikt a pošle nový report.")
        sha = git(tree, "rev-parse", "HEAD")
        pushed = git(tree, "push", "origin", f"HEAD:refs/heads/{target}", timeout=TIMEOUT, optional=True) is not None
        return sha, pushed
    finally:
        git(root, "worktree", "remove", "--force", str(tree), optional=True)
        shutil.rmtree(tree, ignore_errors=True)
        git(root, "worktree", "prune", optional=True)


def _checked_out(git, root, target):
    return f"branch refs/heads/{target}" in git(root, "worktree", "list", "--porcelain").splitlines()


def merge(service, project, ticket_id, now, *, git=gitio.git):
    with LOCK:
        ticket = work_mod.get(service, project, ticket_id)
        work = ticket["work"]
        if work.get("merged"):
            return ticket
        head, target = _precheck(git, work)
        root, remote = work["repository"], f"origin/{target}"
        git(root, "fetch", "origin", target, timeout=TIMEOUT, optional=True)
        if _rev(git, root, remote) and _ancestor(git, root, head, remote):  # merge proběhl, zápis ne: dožene se
            merged = {"sha": _merge_commit(git, root, head, remote), "target": target, "at": now, "by": "opora"}
            return _record(service, project, ticket_id, merged, now)
        target_sha = work["mergeAllowed"]["targetSha"]
        if _rev(git, root, target) != target_sha:
            raise WorkError("target_moved", 409, f"Cíl {target} se od povolení posunul.",
                            "Člověk povolí začlenění znovu (allow-merge).")
        # shortcut: místo oddělení nepřijatých změn jiných úkolů jen kontrola, že báze úkolu je ve špičce cíle (M3).
        if not _ancestor(git, root, work["baseSha"], target_sha):
            raise WorkError("not_allowed", 409, f"Báze úkolu {work['baseSha'][:7]} není ve špičce {target}.",
                            "Větev musí vycházet z cíle; nejdřív začleňte rodiče.")
        tree = Path(service.root) / "pletor" / "linie" / "merge" / ticket_id
        sha, pushed = _operate(git, root, tree, head, work["branch"], target, target_sha)
        if not pushed:
            git(root, "fetch", "origin", target, timeout=TIMEOUT, optional=True)
            if not (_rev(git, root, remote) and _ancestor(git, root, head, remote)):
                raise WorkError("push_failed", 409, f"Push do origin/{target} selhal; nic se nezapsalo.",
                                "Ověřte přístup k origin a zavolejte merge znovu.")
            sha = _merge_commit(git, root, head, remote)
        if not _checked_out(git, root, target):  # lokální ref cíle jen když ho nedrží žádný strom
            git(root, "update-ref", f"refs/heads/{target}", sha, target_sha, optional=True)
        return _record(service, project, ticket_id, {"sha": sha, "target": target, "at": now, "by": "opora"}, now)
