"""Práce ticketu na Linii: jediný zapisovatel `tickets.work` (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §2–§3).

Ticket = kulička. `create` založí ticket `issued` s `work` (člověk z editoru), `attach` doplní `work` existujícímu
ticketu (srdce vydává bránou). `report` ověří commit proti gitu a uloží `headSha` + kontroly k tomuto SHA; `accept`,
`allow_merge`, `block`/`defer`/`resume` mění jen záznam. Začlenění provádí `merge.py`; `merged` nikdy nepíše klient.
Každé odmítnutí je `WorkError` (kód, HTTP stav, česká zpráva) – podtřída `GateError`, takže ji brána vrací stejně.
"""
import re
import uuid
from contextlib import contextmanager

from backend.agi_pletor.linie import rows, tree, work_state
from backend.brain_opora.determinism import gate
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.ticket_model import body_payload
from backend.integrations.gitio import git
from backend.paths import REPO_ROOT
from database.repositories.tickets import TicketStore

TIMEOUT = 15
SHA = re.compile(r"[0-9a-fA-F]{7,40}")
STATUSES = ("green", "red", "pending")
HINT = "Stav a povolený další krok vrací GET /api/pletor/linie/work/{ticketId}."


class WorkError(GateError):
    def __init__(self, code, status, message, hint=HINT):
        super().__init__(status, code, message, hint)


def rev(root, ref):
    """Plné SHA commitu `ref`, nebo None (neexistuje / vypadá jako přepínač)."""
    if not isinstance(ref, str) or not ref or ref.startswith("-"):
        return None
    return git(root, "rev-parse", "--verify", "-q", ref + "^{commit}", timeout=TIMEOUT, optional=True) or None


def ancestor(root, older, newer):
    return git(root, "merge-base", "--is-ancestor", older, newer, timeout=TIMEOUT, optional=True) is not None


def view(ticket, target_sha=None):
    """Ticket s odvozeným stavem kuličky (`state`, `stateLabel`, `next`)."""
    found = work_state.state(ticket.get("work"), target_sha)
    return {**ticket, "state": found["state"], "stateLabel": found["label"], "next": found["next"]}


@contextmanager
def store_for(service, project):
    """Zápis: zámek projektu + transakce."""
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            yield TicketStore(db, project)


def _ticket(store, ticket_id, need_work=True):
    ticket = store.get(ticket_id)
    if ticket is None:
        raise WorkError("ticket_not_found", 404, "Ticket v projektu neexistuje.", "ID ticketu vrací GET /board.")
    if need_work and not ticket.get("work"):
        raise WorkError("work_missing", 409, "Ticket nemá práci Linie.", "Připojte ji přes POST /work/{ticketId}/attach.")
    return ticket


def get(service, project, ticket_id):
    with service.reading(project):
        return view(_ticket(TicketStore(service.db_for(project), project), ticket_id))


def _name(value, key):
    if not isinstance(value, str) or value.startswith("-") or git(None, "check-ref-format", "--branch", value,
                                                                   optional=True) is None:
        raise WorkError("invalid_payload", 422, f"{key} je platný název větve.", 'Například "feat/datovy-uzel".')
    return value


def _mark(service, project, ticket_id):
    """Vodotisk cesty `OP-XXXXXX` z UUID ticketu; při kolizi s jiným ticketem projektu dalších 6 znaků."""
    taken = {t["work"].get("mark") for t in _all(service, project)}
    mark = "OP-" + ticket_id[3:9].upper()
    return mark if mark not in taken else "OP-" + ticket_id[9:15].upper()


def _new_work(service, project, root, work_in, ticket_id):
    if work_in.get("rowId") not in {row["id"] for row in rows.read(service.root, project)["rows"]}:
        raise WorkError("row_not_found", 404, "Řádek Linie neexistuje.", "Řádky vrací GET /board.")
    branch = _name(work_in.get("branch"), "branch")
    out = git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)", timeout=TIMEOUT, optional=True) or ""
    heads = set(out.split())
    base = _name(work_in["baseBranch"], "baseBranch") if work_in.get("baseBranch") else tree.parent(branch, heads)
    if not tree.is_child(branch, base, heads):
        raise WorkError("branch_hierarchy", 422, f"{branch} vzniká z {tree.parent(branch, heads)}, ne z {base}.",
                        "Větev vzniká z rodiče podle jména (feat/a-b z feat/a); baseBranch lze vynechat.")
    target = _name(work_in["target"], "target") if work_in.get("target") else base
    if not tree.may_merge(branch, target, base, heads):
        raise WorkError("target_not_parent", 422, f"{branch} se začleňuje do {tree.parent(branch, heads, base)}, "
                        f"ne do {target}.", "Cíl vynechte, nebo zvolte rodiče větve.")
    base_sha = rev(root, base)
    if not base_sha:
        raise WorkError("base_missing", 422, f"Výchozí větev {base} v repozitáři neexistuje.", "Zvolte main, develop "
                        "nebo existující větev rodiče.")
    # shortcut: repozitář je vždy OPORA sama (REPO_ROOT); `sourcePath` projektu až v M3.
    return {"rowId": work_in["rowId"], "title": (work_in.get("title") or "").strip() or None, "repository": str(root),
            "worktree": None, "mark": _mark(service, project, ticket_id), "runs": [], "branch": branch, "baseBranch": base, "baseSha": base_sha, "headSha": None,
            "target": target, "checks": [], "preview": None, "acceptance": None, "mergeAllowed": None,
            "merged": None, "blocked": None, "deferred": False}


def create(service, project, workspace, body, work_in, now, *, root=None):
    """Nový ticket `issued` s `work`; větev se nezakládá (založí ji agent z `baseBranch@baseSha`)."""
    worker_body = body_payload(body)
    if not gate.workspace_known(service, project, workspace):
        raise WorkError("workspace_not_found", 404, "Pracovní prostor v projektu neexistuje.", "Použijte main.")
    new_id = "tk_" + uuid.uuid4().hex
    work = _new_work(service, project, root or REPO_ROOT, work_in, new_id)
    with store_for(service, project) as store:
        store.insert(new_id, workspace, "issued", worker_body, {"pins": []}, now)
        store.set_work(new_id, work, now)
        return view(store.get(new_id))


def attach(service, project, ticket_id, work_in, now, *, root=None):
    work = _new_work(service, project, root or REPO_ROOT, work_in, ticket_id)
    with store_for(service, project) as store:
        if _ticket(store, ticket_id, need_work=False).get("work"):
            raise WorkError("work_exists", 409, "Ticket už práci Linie má.")
        store.set_work(ticket_id, work, now)
        return view(store.get(ticket_id))


def _change(service, project, ticket_id, now, change):
    with store_for(service, project) as store:
        ticket = _ticket(store, ticket_id)
        work = change(ticket)
        if work != ticket["work"]:
            store.set_work(ticket_id, work, now)
        return view(store.get(ticket_id))


def apply_report(work, sha, checks, worktree, now, by):
    """`work` s novou hlavou: `sha` musí existovat, ležet nad `baseSha` a na větvi úkolu, jinak 409 `work_mismatch`."""
    root = work["repository"]
    full = rev(root, sha) if isinstance(sha, str) and SHA.fullmatch(sha) else None
    if not (full and ancestor(root, work["baseSha"], full) and ancestor(root, full, work["branch"])):
        raise WorkError("work_mismatch", 409, f"Commit {sha} neleží na větvi {work['branch']} nad bází "
                        f"{work['baseSha'][:7]}.", "Commitujte na větvi úkolu a pošlete git rev-parse HEAD.")
    if work.get("merged"):
        if full == work["headSha"]:
            return work
        raise WorkError("work_merged", 409, "Práce je už začleněná; další commit patří do nového úkolu.")
    runs, who = work.get("runs") or [], by.split(":", 1)[-1]
    mine = [r for r in runs if r.get("agent") == who] or runs  # relace téhož agenta, jinak poslední vůbec
    run_id = mine[-1]["runId"] if mine else None
    fresh = []
    for check in checks or []:
        name, status = check.get("name"), check.get("status")
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or status not in STATUSES:
            raise WorkError("invalid_payload", 422, "Kontrola je {name, status: green|red|pending}.")
        fresh.append({"name": name.strip(), "status": status, "sha": full, "at": now, "by": by, "runId": run_id})
    names = {check["name"] for check in fresh}
    kept = [check for check in work["checks"] if not (check["sha"] == full and check["name"] in names)]
    return {**work, "headSha": full, "headRunId": run_id, "checks": kept + fresh,
            "worktree": worktree or work.get("worktree")}


def report(service, project, ticket_id, sha, checks, worktree, now, by):
    """Commit (a kontroly k němu) na větvi úkolu. Kuličku neuzavírá."""
    return _change(service, project, ticket_id, now,
                   lambda ticket: apply_report(ticket["work"], sha, checks, worktree, now, by))


def run(service, project, ticket_id, payload, now):
    """Relace LLM na úkolu: nové `sessionId` přidá záznam (zamkne `fromSha` a revizi zadání), stejné ho jen osvěží."""
    def change(ticket):
        work, runs = ticket["work"], list(ticket["work"].get("runs") or [])
        old = next((r for r in runs if r["sessionId"] == payload["sessionId"]), None)
        record = {"runId": "run_" + uuid.uuid4().hex, "sessionId": payload["sessionId"], "startedAt": now,
                  "fromSha": rev(work["repository"], work["branch"]), "revision": ticket["machine"].get("cardVersion"),
                  **(old or {}), "agent": payload.get("agent") or (old or {}).get("agent"),
                  "transcriptPath": payload.get("transcriptPath") or (old or {}).get("transcriptPath")}
        return {**work, "runs": [record if r is old else r for r in runs] + ([] if old else [record])}
    return _change(service, project, ticket_id, now, change)


def accept(service, project, ticket_id, sha, note, now):
    """Přijetí přesně aktuální hlavy (`sha == headSha`, i zkrácené), s revizí zadání. Nic neslučuje."""
    def change(ticket):
        work, head = ticket["work"], ticket["work"].get("headSha")
        if not head or not isinstance(sha, str) or len(sha) < 7 or not head.startswith(sha.lower()):
            raise WorkError("head_moved", 409, f"Revize {sha} není aktuální hlava {(head or 'žádná')[:7]}.",
                            "Načtěte kuličku znovu a přijměte aktuální headSha.")
        return {**work, "acceptance": {"sha": head, "revision": ticket["machine"]["cardVersion"], "by": "human",
                                       "at": now, "note": note or ""}}
    return _change(service, project, ticket_id, now, change)


def revoke_accept(service, project, ticket_id, now):
    return _change(service, project, ticket_id, now,
                   lambda ticket: {**ticket["work"], "acceptance": None, "mergeAllowed": None})


def allow_merge(service, project, ticket_id, target, now):
    """Povolení začlenit přijatou hlavu do `target` se špičkou cíle v tuto chvíli (`targetSha`)."""
    def change(ticket):
        work = ticket["work"]
        if not work.get("acceptance"):
            raise WorkError("no_acceptance", 409, "Začlenění jde povolit až po přijetí revize.")
        if work["acceptance"]["sha"] != work.get("headSha"):
            raise WorkError("head_moved", 409, "Přijetí platí pro starší hlavu; přijměte aktuální revizi znovu.")
        aim = _name(target or work.get("target"), "target")
        tip = rev(work["repository"], aim)
        if not tip:
            raise WorkError("target_missing", 422, f"Cílová větev {aim} v repozitáři neexistuje.")
        return {**work, "target": aim, "mergeAllowed": {"target": aim, "targetSha": tip, "sourceSha": work["headSha"],
                                                        "by": "human", "at": now}}
    return _change(service, project, ticket_id, now, change)


def block(service, project, ticket_id, reason, now):
    return _change(service, project, ticket_id, now,
                   lambda ticket: {**ticket["work"], "blocked": {"reason": reason, "at": now}})


def defer(service, project, ticket_id, now):
    return _change(service, project, ticket_id, now, lambda ticket: {**ticket["work"], "deferred": True})


def resume(service, project, ticket_id, now):
    return _change(service, project, ticket_id, now,
                   lambda ticket: {**ticket["work"], "blocked": None, "deferred": False})


def set_preview(service, project, ticket_id, record, now):
    return _change(service, project, ticket_id, now,
                   lambda ticket: {**ticket["work"], "preview": {"slug": record["slug"], "sha": record["sha"]}})


def _all(service, project):
    with service.reading(project):
        return TicketStore(service.db_for(project), project).list_with_work()


def accepted(service, project):
    """`{větev: work.acceptance}` přes celý projekt (novější ticket vyhrává) pro souhrn a graf Velínu."""
    return {t["work"]["branch"]: t["work"]["acceptance"] for t in _all(service, project) if t["work"].get("acceptance")}


def used_rows(service, project):
    """Řádky, na kterých leží aspoň jedna kulička (ty nejde smazat)."""
    return {t["work"]["rowId"] for t in _all(service, project)}
