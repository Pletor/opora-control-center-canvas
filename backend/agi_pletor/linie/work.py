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

L7e (§7 bod 5): každá změna `work` zapíše v téže transakci událost deníku `linie.*` (`journal.py`) s původcem `by`;
`block` / `defer` / `unblock` / `resume` / `abandon` běží i bez gitu (git jen `optional`). `requestId` váže práci na
žádost srdci (`requests.py`); `attempts[]` plní `attempt.py`.

L7d (§7 bod 4, `plan_link.py`): `create` / `attach` zmrazí `work.issued = {cardId, cardRevision, at}` (revizi čte
server), `accept` uloží dvojici `(sha, cardRevision)`, smaže povolení začlenění a staré přijetí přesune do
`work.acceptanceHistory[]`; `view` nese `plan = {state, planCardId, directionCardId, cardRevision, issued, text, diff}`.

Zkouška (docs/navrhy/2026-11-08-linie-zkouska.md §3–§8): `view` nese `work.preview = {slug, sha, url, state, at}` se
stavem z registru náhledů a odvozené `trial` (stav náhledu proti hlavě, `tried`, novinky `tried.sha..hlava`). `tried`
zapíše SHA běžícího náhledu, `accept` bez zkoušky hlavy odmítne 409 `not_tried` (kromě výslovného `untested`).
`follow_preview` po reportu (routa i brána) restartuje existující náhled na novou hlavu; selhání jen zaloguje.
Doplněk: report nese `tryout = {at, steps}` (místo v aplikaci jako query a kroky); uloží se jako `work.tryout` s SHA,
report bez něj převezme předchozí. `trial.url` = URL náhledu + `tryout.at`, `trial.steps` = kroky.
"""
import logging
import os
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from backend.agi_pletor.linie import (
    deploy,
    evaluate,
    gitsnap,
    journal,
    merge_log,
    plan_link,
    previews,
    rows,
    tree,
    work_state,
)
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
NEWS = 10  # novinek od poslední zkoušky v `trial.news`, zbytek jen počtem
TRYOUT_AT, TRYOUT_STEPS, TRYOUT_STEP = 300, 8, 200  # meze `tryout`: délka query, počet kroků, délka kroku
LOG = logging.getLogger(__name__)


class WorkError(GateError):
    def __init__(self, code, status, message, hint=HINT):
        super().__init__(status, code, message, hint)


def rev(root, ref):
    """Plné SHA commitu `ref`, nebo None (neexistuje / vypadá jako přepínač)."""
    if not isinstance(ref, str) or not ref or ref.startswith("-"):
        return None
    return gitsnap.rev(root, ref)


def tip(root, branch, fetch=False):
    """Špička cíle = origin (pravda); lokální ref jen když origin větev nezná. `fetch` jen tam, kde se zapisuje."""
    if fetch:
        git(root, "fetch", "origin", branch, timeout=TIMEOUT, optional=True)
    return rev(root, "origin/" + branch) or rev(root, branch)


def ancestor(root, older, newer):
    return gitsnap.ancestor(root, older, newer)


def unreported(work, integ=None, squashed=()):
    """`(sha, git_ok)`: skutečná špička větve, kterou hlášení nepokrývá (L7 §2a HEAD = špička podle gitu), jinak None.

    Po začlenění je to nejnovější commit, který merge neobsahuje; před ním špička `rev(branch)`, když se liší od
    `headSha`. Nedostupná špička u nahlášené nezačleněné práce = `git_ok: False` (HEAD zůstává `headSha`).
    `squashed` = zdrojové hlavy hotových squashů do cíle (merge log): ty commity jsou v cíli, i když ne jako předci."""
    merged = integ["state"] == "merged" if integ else bool(work.get("merged"))
    if not work.get("branch"):
        return None, True
    if merged:
        # OP-43F5B0.2: začleněná hlava = headSha (merge chce headSha == přijatá == špička); squash ji v cíli nemá
        sha = work.get("headSha") or (integ["sha"] if integ else work["merged"].get("sha"))
        new = gitsnap.range_tip(work["repository"], sha, work["branch"]) if sha else None
        # §10.2: commit po merge, který už v cíli leží (začlenila ho další kulička téže větve), větev znovu neotvírá
        target = (integ or {}).get("target") or (work.get("merged") or {}).get("target") or work.get("target")
        refs = (target, "origin/" + target, *squashed) if target else squashed
        if new and any(ancestor(work["repository"], new, ref) for ref in refs):
            new = None
        return new, True
    if not work.get("headSha"):
        return None, True
    # OP-020DBE.2: přijetí i kontroly se hodnotí proti špičce větve, ne proti poslednímu hlášení
    tip = rev(work["repository"], work["branch"])
    return (tip if tip and tip != work["headSha"] else None), bool(tip)


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


def folder(service):
    """Složka Pletoru (`<data>/pletor`) s registrem náhledů."""
    return Path(service.root) / "pletor"


def live_preview(service, work, running=None):
    """`work.preview` se stavem z registru náhledů (`running` = `previews.status`, přečtené jednou); záznam, který
    z registru zmizel, je `stopped`."""
    stored = work.get("preview")
    if not stored:
        return None
    found = next((r for r in (previews.status(folder(service)) if running is None else running)
                  if r.get("slug") == stored.get("slug")), None)
    if found is None:
        return {**stored, "url": stored.get("url"), "state": "stopped", "at": stored.get("at")}
    return {"slug": found["slug"], "sha": found.get("sha"), "url": found.get("url"), "state": found.get("state"),
            "at": found.get("startedAt")}


def trial(work, preview, head):
    """Zkouška hlavy (§4, §7, §8): stav náhledu proti hlavě, poslední zkouška a novinky `tried.sha..hlava`."""
    shown = preview if preview and preview.get("state") != "stopped" else None
    state = "none" if not shown else shown["state"] if shown["state"] in ("building", "failed") else (
        "current" if shown.get("sha") == head else "stale")
    tried = work.get("tried")
    news = []
    if tried and head and tried["sha"] != head:
        out = gitsnap.frozen(work["repository"], "log", "--format=%H%x1f%s", f"{tried['sha']}..{head}") or ""
        news = [dict(zip(("sha", "subject"), line.split("\x1f", 1))) for line in out.splitlines()]
    tryout = work.get("tryout") or {}
    return {"state": state, "url": with_at((shown or {}).get("url"), tryout.get("at")),
            "sha": (shown or {}).get("sha"), "head": head, "tried": tried,
            "triedCurrent": bool(tried and head and tried["sha"] == head),
            "news": news[:NEWS], "newsMore": max(0, len(news) - NEWS), "steps": tryout.get("steps") or []}


def with_at(url, at):
    """URL náhledu s místem `at` (query); klíče, které URL už má (`project`, `workspace`), se nezdvojují."""
    if not url or not at:
        return url
    query = urlsplit(url).query
    have = {key for key, _ in parse_qsl(query)}
    extra = urlencode([(key, value) for key, value in parse_qsl(at) if key not in have])
    return f"{url}{'&' if query else '?'}{extra}" if extra else url


def tryout_of(raw, sha):
    """`{at, steps}` z reportu → `work.tryout = {at, steps, sha}`; `at` je jen query bez schématu a hostu, jinak 422."""
    bad = WorkError("invalid_payload", 422, f"tryout je {{at: query do {TRYOUT_AT} znaků (např. "
                    f"\"screen=pletor&part=linie\"), steps: nejvýš {TRYOUT_STEPS} kroků do {TRYOUT_STEP} znaků}}.")
    if not isinstance(raw, dict) or not set(raw) <= {"at", "steps"}:
        raise bad
    at, steps = raw.get("at") or "", raw.get("steps") or []
    if not isinstance(at, str) or len(at) > TRYOUT_AT or at.startswith(("?", "/", "#")):
        raise bad
    parts = urlsplit(at)
    if at and (parts.scheme or parts.netloc or parts.fragment or not parse_qsl(at)):
        raise bad  # odkaz Vyzkoušet nesmí vést mimo náhled
    if not isinstance(steps, list) or len(steps) > TRYOUT_STEPS or not all(
            isinstance(step, str) and step.strip() and len(step) <= TRYOUT_STEP for step in steps):
        raise bad
    return {"at": at, "steps": [step.strip() for step in steps], "sha": sha}


def facts(service, project, ticket, pr=None, log=None, events=None, graph=None, running=None):
    """Data kuličky mimo ticket (merge log, nasazení, živost relace, vazba na plán, náhled); board předá log, události,
    graf prostoru a registr náhledů přečtené jednou."""
    work = ticket.get("work")
    if not work:
        return {}
    log = merge_log.read(service.root, project) if log is None else log
    events = deploy.read(service.root, project) if events is None else events
    integ = integration(work, log, ticket["ticketId"], pr)
    allowed = work.get("mergeAllowed")
    squashed = [e["started"]["source_sha"] for e in log if (e.get("finished") or {}).get("ok")
                and e["started"].get("mode") == "squash" and e["started"]["target"] == integ["target"]]
    return {"integration": integ, "deploy": deployed(work, integ, events), "squashed": squashed,
            "preview": live_preview(service, work, running),
            "live": any(live(run) for run in work.get("runs") or []),
            "targetSha": tip(work["repository"], allowed["target"]) if allowed else None,
            "plan": plan_link.resolve(service, project, ticket, graph)}


def view(ticket, sources=None, pr=None, facts=None):
    """Ticket s osami, souhrnem, povolenými akcemi a důkazy z jednoho `evaluate` (L7 §4); staré `state`, `stateLabel`,
    `next` zůstávají pro frontend do L7b. `facts` z `facts()`; bez nich osy jen ze záznamu ticketu."""
    work, facts = ticket.get("work") or {}, facts or {}
    integ = facts.get("integration")
    after, git_ok = unreported(work, integ, facts.get("squashed") or ()) if work else (None, True)
    plan = facts.get("plan")
    found = evaluate.evaluate(work, after, facts.get("live", False), integ, facts.get("deploy"),
                              facts.get("targetSha"), (plan or {}).get("cardRevision"))
    sources = sources or local_sources(tokens.stamp())
    if not git_ok:
        sources = {**sources, "git": {**sources["git"], "ok": False}}
    shipped = [{"kind": "deploy", "ref": f"{env}@{e['sha'][:7]}", "at": e["at"],
                "src": "událost prostředí" if e["origin"] == "environment" else "hlášeno člověkem"}
               for env, e in (facts.get("deploy") or {}).items()]
    preview = facts["preview"] if "preview" in facts else work.get("preview")
    return {**ticket, "work": {**work, "preview": preview} if work else ticket.get("work"),
            "trial": trial(work, preview, found["axes"]["work"]["sha"]) if work else None,
            "state": work_state.LEGACY[found["key"]], "stateLabel": found["text"], "next": found["next"],
            "axes": found["axes"], "summary": {key: found[key] for key in ("key", "text", "reason", "next")},
            "allowed": found["allowed"], "blocked": found["blocked"],
            "incomplete": incomplete(sources),
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
    stored, tickets = rows.read(service.root, project)["rows"], _all(service, project)
    row = next((r for r in stored if r["id"] == work_in.get("rowId")), None)
    held = {t["work"]["branch"] for t in tickets if row and t["work"]["rowId"] == row["id"]}
    held |= {row["branch"]} if row and row.get("branch") else set()
    if row and (not held or branch in held):
        return row["id"]
    # řádek = větev: další kulička téže větve jde na její řádek (podle větve, kuliček nebo jména), ne na nový duplikát
    for other in stored:
        mine = {t["work"]["branch"] for t in tickets if t["work"]["rowId"] == other["id"]} | ({other["branch"]} if other.get("branch") else set())
        if branch in mine or (not mine and other.get("name") == branch):
            return other["id"]
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
            "merged": None, "blocked": None, "deferred": False, "requestId": work_in.get("requestId"), "attempts": []}


def create(service, project, workspace, body, work_in, now, *, root=None, ticket_id=None):
    """Nový ticket `issued` s `work`; větev se nezakládá (založí ji agent z `baseBranch@baseSha`). `ticket_id`
    (z idempotenčního klíče): už založený ticket se jen vrátí."""
    worker_body = body_payload(body)
    if not gate.workspace_known(service, project, workspace):
        raise WorkError("workspace_not_found", 404, "Pracovní prostor v projektu neexistuje.", "Použijte main.")
    new_id = ticket_id or "tk_" + uuid.uuid4().hex
    with service.reading(project):
        if TicketStore(service.db_for(project), project).get(new_id):
            return get(service, project, new_id)
    work = _new_work(service, project, root or REPO_ROOT, work_in, new_id, auto_row=True)
    work["issued"] = {"cardId": None, "cardRevision": None, "at": now}  # editor vydává bez karty plánu
    with store_for(service, project) as store:
        store.insert(new_id, workspace, "issued", worker_body, {"pins": []}, now)
        store.set_work(new_id, work, now)
        journal.write(store.db, project, "linie.work.created", "human",
                      {"ticket": new_id, "request": work["requestId"]}, workspace, branch=work["branch"])
        return present(service, project, store.get(new_id))


def attach(service, project, ticket_id, work_in, now, *, root=None):
    """`work` existujícímu ticketu se zmrazenou referencí `issued` na kartu (revizi čte server, L7d)."""
    work = _new_work(service, project, root or REPO_ROOT, work_in, ticket_id)
    with store_for(service, project) as store:
        ticket = _ticket(store, ticket_id, need_work=False)
        if ticket.get("work"):
            raise WorkError("work_exists", 409, "Ticket už práci Linie má.")
        store.set_work(ticket_id, {**work, "issued": plan_link.issue(service, project, ticket, now)}, now)
        journal.write(store.db, project, "linie.work.attached", "human",
                      {"ticket": ticket_id, "request": work["requestId"]}, ticket["workspaceId"], branch=work["branch"])
        return present(service, project, store.get(ticket_id))


def _change(service, project, ticket_id, now, change, kind=None, by=None, **refs):
    """Změna `work` v transakci; s `kind` zapíše událost deníku, jen když se `work` opravdu změnilo."""
    with store_for(service, project) as store:
        ticket = _ticket(store, ticket_id)
        work = change(ticket)
        if work != ticket["work"]:
            store.set_work(ticket_id, work, now)
            if kind:
                journal.write(store.db, project, kind, by, {"ticket": ticket_id, **refs}, ticket["workspaceId"])
        return present(service, project, store.get(ticket_id))


def on_branch(work, sha):
    """Plné sha commitu nad `baseSha` na větvi úkolu, jinak 409 `work_mismatch`."""
    root = work["repository"]
    full = rev(root, sha) if isinstance(sha, str) and SHA.fullmatch(sha) else None
    if not (full and ancestor(root, work["baseSha"], full) and ancestor(root, full, work["branch"])):
        raise WorkError("work_mismatch", 409, f"Commit {sha} neleží na větvi {work['branch']} nad bází "
                        f"{work['baseSha'][:7]}.", "Commitujte na větvi úkolu a pošlete git rev-parse HEAD.")
    return full


def apply_report(work, sha, checks, worktree, now, by, tryout=None):
    """`work` s novou hlavou: `sha` musí existovat, ležet nad `baseSha` a na větvi úkolu, jinak 409 `work_mismatch`.
    `tryout` (`{at, steps}`) nahradí `work.tryout`; bez něj zůstane předchozí."""
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
            "worktree": worktree or work.get("worktree"),
            **({"tryout": tryout_of(tryout, full)} if tryout is not None else {})}


def report(service, project, ticket_id, sha, checks, worktree, now, by, tryout=None):
    """Commit (a kontroly k němu) na větvi úkolu. Kuličku neuzavírá; existující náhled dožene novou hlavu."""
    shown = _change(service, project, ticket_id, now,
                    lambda ticket: apply_report(ticket["work"], sha, checks, worktree, now, by, tryout),
                    "linie.report", by,
                    sha=sha)
    return follow_preview(service, project, ticket_id, now) or shown


def follow_preview(service, project, ticket_id, now):
    """Po reportu (routa i brána, mimo zámek a transakci): náhled, který kulička má a není `stopped`, se restartuje
    na novou hlavu. Vrací kuličku po restartu, jinak None; selhání restartu report neshodí, jen se zaloguje."""
    try:
        with service.reading(project):
            work = (TicketStore(service.db_for(project), project).get(ticket_id) or {}).get("work") or {}
        preview = live_preview(service, work)
        # OP-43F5B0.3: člověk zkouší přesně aktuální hlavu; první spuštění zůstává jeho, restart dělá služba
        if not preview or preview["state"] == "stopped" or not work.get("headSha") or preview["sha"] == work["headSha"]:
            return None
        record = previews.start(folder(service), work["repository"], work["branch"], project, service.root, now)
        journal.record(service, project, "linie.preview.restarted", "opora", {"ticket": ticket_id, "sha": record["sha"]})
        return set_preview(service, project, ticket_id, record, now)
    except Exception:  # náhled je pomůcka, report už je zapsaný
        LOG.exception("Restart náhledu %s po reportu selhal", ticket_id)
        return None


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


def accept(service, project, ticket_id, sha, note, now, untested=False):
    """Přijetí přesně aktuální hlavy (`sha` == skutečná špička větve, i zkrácené), s revizí zadání. Nic neslučuje.
    Hlava musí být vyzkoušená (`work.tried`), jinak 409 `not_tried`; `untested` = výslovně bez zkoušky."""
    def change(ticket):
        work, shown = ticket["work"], present(service, project, ticket)
        head = shown["axes"]["work"]["sha"]  # skutečná špička větve, ne jen poslední hlášení
        if not head or not isinstance(sha, str) or len(sha) < 7 or not head.startswith(sha.lower()):
            raise WorkError("head_moved", 409, f"Revize {sha} není aktuální hlava {(head or 'žádná')[:7]}.",
                            "Načtěte kuličku znovu a přijměte aktuální headSha.")
        require(shown, "accept")  # jen ověřenou revizi (checks.passed pro HEAD, L7 §8)
        tried = (work.get("tried") or {}).get("sha")
        # OP-43F5B0.7: přijímá se to, co člověk vyzkoušel; nevyzkoušené jen výslovně
        if tried != head and not untested:
            said = f"Vyzkoušeno na {tried[:7]}, hlava je {head[:7]}." if tried else f"Nevyzkoušeno, hlava je {head[:7]}."
            raise WorkError("not_tried", 409, said + " Vyzkoušejte hlavu v náhledu, nebo přijměte výslovně bez zkoušky.",
                            "Vyzkoušet (POST /work/{ticketId}/tried), nebo accept s untested: true.")
        # OP-8A69A3.accept: přijetí platí pro dvojici (sha, cardRevision); revize je táž, kterou ověřil require
        card = (shown["plan"] or {}).get("cardRevision")
        return {**_archived(work), "mergeAllowed": None,
                "acceptance": {"sha": head, "cardRevision": card, "revision": ticket["machine"]["cardVersion"],
                               "by": "human", "at": now, "note": note or "", "tested": None if untested else tried}}
    return _change(service, project, ticket_id, now, change, "linie.accept", "human", sha=sha)


def _archived(work):
    """Dosavadní přijetí zůstává historickým záznamem v `work.acceptanceHistory[]`."""
    old = work.get("acceptance")
    return {**work, "acceptanceHistory": (work.get("acceptanceHistory") or []) + ([old] if old else [])}


def revoke_accept(service, project, ticket_id, now):
    def change(ticket):
        require(present(service, project, ticket), "revoke_accept")  # jen platné přijetí HEAD před začleněním
        return {**_archived(ticket["work"]), "acceptance": None, "mergeAllowed": None}
    return _change(service, project, ticket_id, now, change, "linie.accept.revoked", "human")


def allow_merge(service, project, ticket_id, target, now):
    """Povolení začlenit přijatou hlavu do `target` se špičkou cíle v tuto chvíli (`targetSha`); špička cíle = origin."""
    def change(ticket):
        work = ticket["work"]
        if not work.get("acceptance"):
            raise WorkError("no_acceptance", 409, "Začlenění jde povolit až po přijetí revize.")
        if work["acceptance"]["sha"] != work.get("headSha"):
            raise WorkError("head_moved", 409, "Přijetí platí pro starší hlavu; přijměte aktuální revizi znovu.")
        require(present(service, project, ticket), "allow_merge")  # jen `accepted` bez povolení pro HEAD (L7 §2a)
        aim = _name(target or work.get("target"), "target")
        top = tip(work["repository"], aim, fetch=True)
        if not top:
            raise WorkError("target_missing", 422, f"Cílová větev {aim} v repozitáři neexistuje.")
        return {**work, "target": aim, "mergeAllowed": {"target": aim, "targetSha": top, "sourceSha": work["headSha"],
                                                        "by": "human", "at": now}}
    return _change(service, project, ticket_id, now, change, "linie.merge.allowed", "human")


def abandon(service, project, ticket_id, sha, why, now, by):
    """Opuštěná práce je evidence rozhodnutí (§5): přidá `{sha, why, at, by}` do `work.abandoned[]`, HEAD, git ani osy
    nemění; opakování pro týž commit důvod přepíše. Hlášená hlava (`headSha`, ověřená při report) se přijme i bez gitu."""
    def change(ticket):
        work = ticket["work"]
        head = work.get("headSha")
        known = head and isinstance(sha, str) and len(sha) >= 7 and head.startswith(sha.lower())
        full = head if known else on_branch(work, sha)
        if not isinstance(why, str) or not why.strip():
            raise WorkError("invalid_payload", 422, "why je neprázdný důvod.")
        kept = [item for item in work.get("abandoned") or [] if item["sha"] != full]
        return {**work, "abandoned": kept + [{"sha": full, "why": why.strip(), "at": now, "by": by}]}
    return _change(service, project, ticket_id, now, change, "linie.abandon", by, sha=sha)


# Rozhodnutí bez gitu (§7 bod 5): jen záznam s původcem; `decided` nese poslední defer / unblock / resume.
def block(service, project, ticket_id, reason, now, by="human"):
    return _change(service, project, ticket_id, now,
                   lambda ticket: {**ticket["work"], "blocked": {"reason": reason, "at": now, "by": by}},
                   "linie.block", by)


def defer(service, project, ticket_id, now, by="human"):
    return _change(service, project, ticket_id, now, lambda ticket: {
        **ticket["work"], "deferred": True, "decided": {"action": "defer", "at": now, "by": by}}, "linie.defer", by)


def unblock(service, project, ticket_id, now, by="human"):
    return _change(service, project, ticket_id, now, lambda ticket: {
        **ticket["work"], "blocked": None, "decided": {"action": "unblock", "at": now, "by": by}}, "linie.unblock", by)


def forget(service, project, ticket_id, now, by="human"):
    """Smaže slepou kuličku (§10.4): jen blokovanou, jejíž commity už leží v cíli nebo žádné nemá. Kód mimo cíl
    kuličku drží – nejdřív větev smažte, nebo kuličku odblokujte a dokončete."""
    with store_for(service, project) as store:
        ticket = _ticket(store, ticket_id)
        w = ticket["work"]
        if not w.get("blocked"):
            raise WorkError("forget_not_blocked", 409, "Zapomenout jde jen blokovanou kuličku.",
                            "Živou práci dokončete, odložte nebo zablokujte s důvodem.")
        head, target = w.get("headSha"), w.get("target")
        # kód je „použitý“, když došel do cíle nebo do kmene (develop) – starý cíl mohl zaniknout při přestavbě stromu
        kept = (target, "origin/" + target, "develop", "origin/develop")
        # OP-43F5B0.2: squash commity větve do cíle nepřenese; použité jsou i ty pod zdrojem hotového squashe
        kept += tuple(e["started"]["source_sha"] for e in merge_log.read(service.root, project)
                      if (e.get("finished") or {}).get("ok") and e["started"].get("mode") == "squash"
                      and e["started"]["target"] in (target, "develop"))
        if head and head != w.get("baseSha") and not any(ancestor(w["repository"], head, ref) for ref in kept):
            raise WorkError("forget_code_alive", 409, f"Commit {head[:7]} není v {target} ani v develop; kuličku drží "
                            "živý kód.",
                            "Smažte větev s nepoužitým kódem, nebo kuličku odblokujte a dokončete.")
        store.delete(ticket_id)
        journal.write(store.db, project, "linie.forget", by, {"ticket": ticket_id, "mark": w.get("mark"),
                                                                "title": w.get("title"), "branch": w.get("branch")},
                      ticket["workspaceId"])
        return {"forgotten": ticket_id, "mark": w.get("mark"), "branch": w.get("branch")}


def resume(service, project, ticket_id, now, by="human"):
    return _change(service, project, ticket_id, now, lambda ticket: {
        **ticket["work"], "blocked": None, "deferred": False, "decided": {"action": "resume", "at": now, "by": by}},
        "linie.resume", by)


def set_preview(service, project, ticket_id, record, now):
    return _change(service, project, ticket_id, now, lambda ticket: {**ticket["work"], "preview": {
        "slug": record["slug"], "sha": record["sha"], "url": record.get("url"), "state": record.get("state"),
        "at": record.get("startedAt")}})


def mark_tried(service, project, ticket_id, now):
    """Člověk otevřel běžící náhled (§6): `work.tried = {sha náhledu, at}` a deník `linie.preview.tried`."""
    preview = get(service, project, ticket_id)["work"]["preview"]
    if not preview or preview["state"] != "running":
        raise WorkError("preview_not_running", 409, "Náhled neběží, není co vyzkoušet.",
                        "Spusťte náhled (POST /work/{ticketId}/preview) a počkejte, až poběží.")
    return _change(service, project, ticket_id, now,
                   lambda ticket: {**ticket["work"], "tried": {"sha": preview["sha"], "at": now}},
                   "linie.preview.tried", "human", sha=preview["sha"])


def _all(service, project):
    with service.reading(project):
        return TicketStore(service.db_for(project), project).list_with_work()


def accepted(service, project):
    """`{větev: work.acceptance}` přes celý projekt (novější ticket vyhrává) pro souhrn a graf Velínu."""
    return {t["work"]["branch"]: t["work"]["acceptance"] for t in _all(service, project) if t["work"].get("acceptance")}


def used_rows(service, project):
    """Řádky, na kterých leží aspoň jedna kulička (ty nejde smazat)."""
    return {t["work"]["rowId"] for t in _all(service, project)}
