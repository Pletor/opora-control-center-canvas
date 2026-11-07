"""Práce ticketu na Linii: jediný zapisovatel `tickets.work` (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §2–§3).

`view` skládá kuličku z jednoho `evaluate` (docs/navrhy/2026-11-06-linie-rebrand.md §2a, §4): osy, souhrn, `allowed` /
`blocked`, `incomplete`, `evidence`; `accept` (a v routě `merge`) odmítne 409 `action_not_allowed`, když to pravidlo zakazuje.

Ticket = kulička. `create` založí ticket `issued` s `work` (člověk z editoru), `attach` doplní `work` existujícímu
ticketu (srdce vydává bránou). `report` ověří commit proti gitu a uloží `headSha` + kontroly k tomuto SHA; `accept`,
`allow_merge`, `block`/`defer`/`resume` mění jen záznam. Začlenění provádí `merge.py`; `merged` nikdy nepíše klient.
Každé odmítnutí je `WorkError` (kód, HTTP stav, česká zpráva) – podtřída `GateError`, takže ji brána vrací stejně.

Data mimo ticket (L7 §5a) skládá `facts`: osa `integration` z merge logu (bez záznamu git / GitHub s `mode: None`),
nasazení z událostí prostředí, živá relace = `run` s worktree a heartbeat mladším než 10 min. `abandon` jen zapíše
rozhodnutí do `work.abandoned[]`; HEAD, git ani osy nemění.

L7d (§7 bod 4, `plan_link.py`): `create` / `attach` zmrazí `work.issued = {cardId, cardRevision, at}` (revizi čte
server), `accept` uloží dvojici `(sha, cardRevision)`, smaže povolení začlenění a staré přijetí přesune do
`work.acceptanceHistory[]`; `view` nese `plan = {state, planCardId, directionCardId, cardRevision, issued, text, diff}`.
"""
import os
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from backend.agi_pletor.linie import deploy, evaluate, merge_log, plan_link, rows, tree, work_state
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.ticket_model import body_payload
from backend.integrations.gitio import git
from backend.paths import REPO_ROOT
from database.repositories.tickets import TicketStore

TIMEOUT = 15
SHA = re.compile(r"[0-9a-fA-F]{7,40}")
STATUSES = ("green", "red", "pending")
STALE_AFTER = 600  # s; zdroj starší než 10 min je „zastaralé“ (L7 §4)
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


def after_merge(work, integ=None):
    """Nejnovější commit větve, který začleněný merge neobsahuje (nová revize po začlenění), jinak None."""
    sha = integ["sha"] if integ and integ["state"] == "merged" else (work.get("merged") or {}).get("sha")
    if not sha or not work.get("branch"):
        return None
    return git(work["repository"], "rev-list", "-1", f"{sha}..{work['branch']}", timeout=TIMEOUT, optional=True) or None


def local_sources(at):
    """Zdroje jednoho ticketu čtené v `at` (DB, git a záznam nasazení teď); PR se tu nečtou."""
    # shortcut: git = čas sestavení (headSha ověřil report, after_merge se čte teď); vlastní čas čtení gitu až s L7 §7.3.
    read = {"verifiedAt": at, "ok": True}
    return {"git": read, "checks": read, "sessions": read, "prs": {"verifiedAt": None, "ok": False}, "deploy": read}


def _age(at, moment):
    return (moment - datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)).total_seconds()


def incomplete(sources, now=None):
    """Zdroje, které selhaly, nikdy nebyly čteny nebo jsou starší než `STALE_AFTER` (L7 §4)."""
    moment = now or datetime.now(UTC)
    return [name for name, source in sources.items()
            if not source.get("ok") or not source.get("verifiedAt") or _age(source["verifiedAt"], moment) > STALE_AFTER]


def live(run, now=None):
    """Relace je živá jen s explicitní vazbou na worktree a heartbeat mladším než `STALE_AFTER` (§5a)."""
    return bool(run.get("worktree") and run.get("heartbeat")
                and _age(run["heartbeat"], now or datetime.now(UTC)) < STALE_AFTER)


def integration(work, log, ticket_id, pr=None):
    """Osa `integration` (§5a): z merge logu; bez záznamu důkaz gitu (HEAD v cíli) nebo GitHubu (PR merged), způsob
    neověřen (`mode: None`). Bez záznamu i bez důkazu `none` – neexistence logu sama nic nedokazuje."""
    logged = merge_log.axis(log, ticket_id)
    if logged:
        return logged
    head, target, merged = work.get("headSha"), work.get("target"), work.get("merged") or {}
    found = {"target": merged.get("target") or target, "sha": None, "at": None, "mode": None, "op": None}
    if head and target and head != work.get("baseSha") and any(
            ancestor(work["repository"], head, ref) for ref in (target, "origin/" + target)):
        return {**found, "state": "merged", "sha": merged.get("sha"), "at": merged.get("at"), "src": "git"}
    if (pr or {}).get("state") == "MERGED":
        return {**found, "state": "merged", "src": "GitHub"}
    return {**found, "state": "none", "src": "git"}


def deployed(work, integ, events):
    """`{env: {sha, at, origin}}`: prostředí, jehož poslední nasazená revize obsahuje revizi úkolu (začleněnou, jinak
    HEAD)."""
    root = work["repository"]
    sha = (integ["sha"] if integ["state"] == "merged" else None) or work.get("headSha")
    mine = deploy.latest([e for e in events if os.path.normcase(e.get("repo") or "") == os.path.normcase(root)])
    return {env: {key: e[key] for key in ("sha", "at", "origin")} for env, e in mine.items()
            if sha and (e["sha"] == sha or ancestor(root, sha, e["sha"]))}


def facts(service, project, ticket, pr=None, log=None, events=None, graph=None):
    """Data kuličky mimo ticket (merge log, nasazení, živost relace, vazba na plán); board předá log, události a graf
    prostoru přečtené jednou."""
    work = ticket.get("work")
    if not work:
        return {}
    log = merge_log.read(service.root, project) if log is None else log
    events = deploy.read(service.root, project) if events is None else events
    integ = integration(work, log, ticket["ticketId"], pr)
    return {"integration": integ, "deploy": deployed(work, integ, events),
            "live": any(live(run) for run in work.get("runs") or []),
            "plan": plan_link.resolve(service, project, ticket, graph)}


def view(ticket, sources=None, pr=None, facts=None):
    """Ticket s osami, souhrnem, povolenými akcemi a důkazy z jednoho `evaluate` (L7 §4); staré `state`, `stateLabel`,
    `next` zůstávají pro frontend do L7b. `facts` z `facts()`; bez nich osy jen ze záznamu ticketu."""
    work, facts = ticket.get("work") or {}, facts or {}
    integ = facts.get("integration")
    after = after_merge(work, integ) if work else None
    plan = facts.get("plan")
    found = evaluate.evaluate(work, after, facts.get("live", False), integ, facts.get("deploy"),
                              (plan or {}).get("cardRevision"))
    shipped = [{"kind": "deploy", "ref": f"{env}@{e['sha'][:7]}", "at": e["at"],
                "src": "událost prostředí" if e["origin"] == "environment" else "hlášeno člověkem"}
               for env, e in (facts.get("deploy") or {}).items()]
    return {**ticket, "state": work_state.LEGACY[found["key"]], "stateLabel": found["text"], "next": found["next"],
            "axes": found["axes"], "summary": {key: found[key] for key in ("key", "text", "reason", "next")},
            "allowed": found["allowed"], "blocked": found["blocked"],
            "incomplete": incomplete(sources or local_sources(tokens.stamp())),
            "evidence": evaluate.evidence(work, after, pr, integ) + shipped,
            "plan": {**plan, "diff": plan_link.diff(plan)} if plan else None}


def present(service, project, ticket, pr=None):
    """`view` se všemi daty kuličky (merge log, nasazení, relace)."""
    return view(ticket, pr=pr, facts=facts(service, project, ticket, pr))


def require(shown, action):
    """409 `action_not_allowed` s důvodem z téhož pravidla, když `evaluate` akci nepovoluje (L7 §2a)."""
    if action not in shown["allowed"]:
        raise WorkError("action_not_allowed", 409, shown["blocked"].get(action) or f"Akce {action} není povolena.")


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
        return present(service, project, _ticket(TicketStore(service.db_for(project), project), ticket_id))


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


def _row_id(service, project, work_in, branch, base, target):
    """Řádek pro kuličku: zadaný, pokud drží tuto větev nebo žádnou; jinak se založí řádek větve (název = větev)."""
    row = next((r for r in rows.read(service.root, project)["rows"] if r["id"] == work_in.get("rowId")), None)
    held = {t["work"]["branch"] for t in _all(service, project) if row and t["work"]["rowId"] == row["id"]}
    held |= {row["branch"]} if row and row.get("branch") else set()
    if row and (not held or branch in held):
        return row["id"]
    kind = "items" if tree.role(branch) == "items" else "work"
    return rows.add(service.root, project, branch, kind, base={"branch": base}, target=target)["id"]


def _new_work(service, project, root, work_in, ticket_id, auto_row=False):
    if (work_in.get("rowId") or not auto_row) and work_in.get("rowId") not in {
            row["id"] for row in rows.read(service.root, project)["rows"]}:
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
    row_id = _row_id(service, project, work_in, branch, base, target) if auto_row else work_in["rowId"]
    return {"rowId": row_id, "title": (work_in.get("title") or "").strip() or None, "repository": str(root),
            "worktree": None, "mark": _mark(service, project, ticket_id), "runs": [], "branch": branch, "baseBranch": base, "baseSha": base_sha, "headSha": None,
            "target": target, "checks": [], "preview": None, "acceptance": None, "mergeAllowed": None,
            "merged": None, "blocked": None, "deferred": False}


def create(service, project, workspace, body, work_in, now, *, root=None):
    """Nový ticket `issued` s `work`; větev se nezakládá (založí ji agent z `baseBranch@baseSha`)."""
    worker_body = body_payload(body)
    if not gate.workspace_known(service, project, workspace):
        raise WorkError("workspace_not_found", 404, "Pracovní prostor v projektu neexistuje.", "Použijte main.")
    new_id = "tk_" + uuid.uuid4().hex
    work = _new_work(service, project, root or REPO_ROOT, work_in, new_id, auto_row=True)
    work["issued"] = {"cardId": None, "cardRevision": None, "at": now}  # editor vydává bez karty plánu
    with store_for(service, project) as store:
        store.insert(new_id, workspace, "issued", worker_body, {"pins": []}, now)
        store.set_work(new_id, work, now)
        return present(service, project, store.get(new_id))


def attach(service, project, ticket_id, work_in, now, *, root=None):
    """`work` existujícímu ticketu se zmrazenou referencí `issued` na kartu (revizi čte server, L7d)."""
    work = _new_work(service, project, root or REPO_ROOT, work_in, ticket_id)
    with store_for(service, project) as store:
        ticket = _ticket(store, ticket_id, need_work=False)
        if ticket.get("work"):
            raise WorkError("work_exists", 409, "Ticket už práci Linie má.")
        store.set_work(ticket_id, {**work, "issued": plan_link.issue(service, project, ticket, now)}, now)
        return present(service, project, store.get(ticket_id))


def _change(service, project, ticket_id, now, change):
    with store_for(service, project) as store:
        ticket = _ticket(store, ticket_id)
        work = change(ticket)
        if work != ticket["work"]:
            store.set_work(ticket_id, work, now)
        return present(service, project, store.get(ticket_id))


def on_branch(work, sha):
    """Plné sha commitu nad `baseSha` na větvi úkolu, jinak 409 `work_mismatch`."""
    root = work["repository"]
    full = rev(root, sha) if isinstance(sha, str) and SHA.fullmatch(sha) else None
    if not (full and ancestor(root, work["baseSha"], full) and ancestor(root, full, work["branch"])):
        raise WorkError("work_mismatch", 409, f"Commit {sha} neleží na větvi {work['branch']} nad bází "
                        f"{work['baseSha'][:7]}.", "Commitujte na větvi úkolu a pošlete git rev-parse HEAD.")
    return full


def apply_report(work, sha, checks, worktree, now, by):
    """`work` s novou hlavou: `sha` musí existovat, ležet nad `baseSha` a na větvi úkolu, jinak 409 `work_mismatch`."""
    full = on_branch(work, sha)
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
    """Relace LLM na úkolu: nové `sessionId` přidá záznam (zamkne `fromSha` a revizi zadání), stejné ho jen osvěží.

    Vazba relace na pokus (§5a) = `{ticket, attempt: runId, repo, worktree, heartbeat}`; heartbeat je `at` posledního
    `run`, `worktree` zůstává, když ho opakování vynechá."""
    def change(ticket):
        work, runs = ticket["work"], list(ticket["work"].get("runs") or [])
        old = next((r for r in runs if r["sessionId"] == payload["sessionId"]), None)
        record = {"runId": "run_" + uuid.uuid4().hex, "sessionId": payload["sessionId"], "startedAt": now,
                  "fromSha": rev(work["repository"], work["branch"]), "revision": ticket["machine"].get("cardVersion"),
                  **(old or {}), "agent": payload.get("agent") or (old or {}).get("agent"),
                  "transcriptPath": payload.get("transcriptPath") or (old or {}).get("transcriptPath"),
                  "worktree": payload.get("worktree") or (old or {}).get("worktree"), "repo": work["repository"],
                  "heartbeat": now}
        return {**work, "runs": [record if r is old else r for r in runs] + ([] if old else [record])}
    return _change(service, project, ticket_id, now, change)


def accept(service, project, ticket_id, sha, note, now):
    """Přijetí přesně aktuální hlavy (`sha == headSha`, i zkrácené), s revizí zadání. Nic neslučuje."""
    def change(ticket):
        work, head = ticket["work"], ticket["work"].get("headSha")
        if not head or not isinstance(sha, str) or len(sha) < 7 or not head.startswith(sha.lower()):
            raise WorkError("head_moved", 409, f"Revize {sha} není aktuální hlava {(head or 'žádná')[:7]}.",
                            "Načtěte kuličku znovu a přijměte aktuální headSha.")
        shown = present(service, project, ticket)
        require(shown, "accept")  # jen ověřenou revizi (checks.passed pro HEAD, L7 §8)
        # OP-8A69A3.accept: přijetí platí pro dvojici (sha, cardRevision); revize je táž, kterou ověřil require
        card = (shown["plan"] or {}).get("cardRevision")
        return {**_archived(work), "mergeAllowed": None,
                "acceptance": {"sha": head, "cardRevision": card, "revision": ticket["machine"]["cardVersion"],
                               "by": "human", "at": now, "note": note or ""}}
    return _change(service, project, ticket_id, now, change)


def _archived(work):
    """Dosavadní přijetí zůstává historickým záznamem v `work.acceptanceHistory[]`."""
    old = work.get("acceptance")
    return {**work, "acceptanceHistory": (work.get("acceptanceHistory") or []) + ([old] if old else [])}


def revoke_accept(service, project, ticket_id, now):
    def change(ticket):
        require(present(service, project, ticket), "revoke_accept")  # jen platné přijetí HEAD před začleněním
        return {**_archived(ticket["work"]), "acceptance": None, "mergeAllowed": None}
    return _change(service, project, ticket_id, now, change)


def allow_merge(service, project, ticket_id, target, now):
    """Povolení začlenit přijatou hlavu do `target` se špičkou cíle v tuto chvíli (`targetSha`)."""
    def change(ticket):
        work = ticket["work"]
        if not work.get("acceptance"):
            raise WorkError("no_acceptance", 409, "Začlenění jde povolit až po přijetí revize.")
        if work["acceptance"]["sha"] != work.get("headSha"):
            raise WorkError("head_moved", 409, "Přijetí platí pro starší hlavu; přijměte aktuální revizi znovu.")
        require(present(service, project, ticket), "allow_merge")  # jen `accepted` bez povolení pro HEAD (L7 §2a)
        aim = _name(target or work.get("target"), "target")
        tip = rev(work["repository"], aim)
        if not tip:
            raise WorkError("target_missing", 422, f"Cílová větev {aim} v repozitáři neexistuje.")
        return {**work, "target": aim, "mergeAllowed": {"target": aim, "targetSha": tip, "sourceSha": work["headSha"],
                                                        "by": "human", "at": now}}
    return _change(service, project, ticket_id, now, change)


def abandon(service, project, ticket_id, sha, why, now, by):
    """Opuštěná práce je evidence rozhodnutí (§5): přidá `{sha, why, at, by}` do `work.abandoned[]`, HEAD, git ani osy
    nemění; opakování pro týž commit důvod přepíše."""
    def change(ticket):
        work = ticket["work"]
        full = on_branch(work, sha)
        if not isinstance(why, str) or not why.strip():
            raise WorkError("invalid_payload", 422, "why je neprázdný důvod.")
        kept = [item for item in work.get("abandoned") or [] if item["sha"] != full]
        return {**work, "abandoned": kept + [{"sha": full, "why": why.strip(), "at": now, "by": by}]}
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
