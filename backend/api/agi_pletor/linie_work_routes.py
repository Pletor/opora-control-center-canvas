"""Editor Linie a vynucení workflow (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3), prefix `/api/pletor/linie`.

Všude `?project=`; `GET /board` a `POST /work` navíc `&workspace=`. Jen člověk: board, řádky, `POST /work`, attach,
preview `{fresh?}`, tried, accept `{untested?}` (i DELETE), allow-merge, accept-merge `{untested?}`. Agent i člověk: `GET /work/{id}`, report, merge (provádí služba),
block / defer / resume, run (relace LLM); čtení bez identity: `GET /commit/{sha}` a `GET /trace/{mark}` (cesta práce
podle vodotisku OP-XXXXXX, 404 `mark_not_found`); agent se prokáže `X-Opora-Actor: agent; name=…` nebo tokenem brány `X-Opora-Gate-Token`
(projekt i prostor ticketu musí sedět), bez identity 428. Odmítnutí je JSON `{error, code, hint}`.
Accept a merge, které jedno vyhodnocení (`evaluate`, docs/navrhy/2026-11-06-linie-rebrand.md §2a) nepovoluje, vrací 409
`action_not_allowed` s důvodem z `blocked`; board a work nesou osy, souhrn, důkazy a `snapshot` (§4).

L7c (§5, §5a): `POST /work/{id}/merge {op?}` (stejné op = žádný další merge), `POST /work/{id}/abandon {sha, why}`
(evidence, HEAD ani osy nemění) a `POST /deploy {env, sha, repo?}` – agent / token brány = `origin: environment`,
člověk = `origin: human`; kdo smí kam, určuje `opora.local.toml` `[linie.deploy]`, jinak 403 `deploy_not_allowed`.

L7e (§7 bod 5): `POST /work {idempotencyKey?, requestId?}`, `POST /work/{id}/attempt` (pokus, agent i člověk),
`/revert {sha, expectedHead, op?}`, `/rebase-note {from, to}` (jen evidence), `/unblock`; klíč nebo `op` se stejným
obsahem vrátí týž záznam, s jiným 409 `idempotency_conflict`. `GET /journal?after=&limit=` = deník `linie.*` (bez
identity). Report navíc označí publikované pokusy a u práce žádosti přidá krok `commit` (`linie/requests.py`).

L7g (§7 bod 7): `POST /work/{id}/accept-merge {sha, op?, note?}` jen člověk – accept → allow_merge → merge v jednom
kroku (`linie/human_queue.py`), zastaví se na prvním 409 s větou a jedinou opravou v `hint`.

L8b (§9): `GET /board.txt?project=&workspace=&mine=` = týž snímek jako `/board` jako text/plain (`linie/board_text.py`),
agent i člověk (identita jako u zápisů, bez ní 428); `mine=1` ponechá jen kuličky volajícího agenta; `all=1` vypíše i
uzavřené řádky (L9b §10.2) s kuličkami. Nic nezapisuje.
"""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.agi_pletor.linie import (
    attempt,
    board,
    board_text,
    commit,
    deploy,
    human_queue,
    idempotency,
    journal,
    merge,
    previews,
    requests,
    revert,
    rows,
    trace,
    work,
)
from backend.api.agi_pletor.models import (
    LinieAbandonIn,
    LinieAcceptIn,
    LinieAcceptMergeIn,
    LinieAllowIn,
    LinieAttachIn,
    LinieAttemptIn,
    LinieBlockIn,
    LinieDeployIn,
    LinieMergeIn,
    LinieRebaseNoteIn,
    LinieReportIn,
    LinieRevertIn,
    LinieRowIn,
    LinieRowPatch,
    LinieRunIn,
    LinieWorkIn,
    LinieWorkPreviewIn,
)
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import require_human
from backend.paths import REPO_ROOT

HUMAN = "Tento krok Linie dělá jen člověk v UI."
BODY = ("essence", "build", "doneCriteria")


def origin(service, request, project, ticket_id=None):
    """Původce zápisu (`human` / `agent:<jméno>`) z tokenu brány nebo hlavičky; bez identity 428. S `ticket_id` musí
    token pracovníka patřit do prostoru ticketu."""
    _check(service, project, "main")
    token = request.headers.get(tokens.HEADER)
    if token:
        session = gate.authenticate(service, token, project, ("worker", "heart"))
        if (ticket_id and work.get(service, project, ticket_id)["workspaceId"] != session["workspace_id"]
                and session.get("role") != "heart"):
            raise GateError(403, "gate_scope", "Ticket patří jinému pracovnímu prostoru.",
                            "Pracujte jen s tickety svého prostoru.")
        return "agent:" + (session.get("worker_name") or session.get("role") or "?")
    if request.state.actor == "human":
        return "human"
    if request.state.actor == "agent":
        return "agent:" + (getattr(request.state, "agent", None) or "?")
    raise GateError(428, "identity_required", "Chybí identita původce.",
                    "Pošlete X-Opora-Actor: agent; name=<jméno> nebo X-Opora-Gate-Token.")


def answer(act):
    try:
        return act()
    except GateError as error:
        return JSONResponse(error.body(), status_code=error.status)


def create_linie_work_router(service, pletor, root=None):
    router = APIRouter(prefix="/api/pletor/linie", tags=["pletor"])
    root = root or REPO_ROOT  # čteno až tady, ať test může podvrhnout repozitář

    def human(request, project, act, workspace="main"):
        require_human(request.state.actor, HUMAN)
        return answer(lambda: (_check(service, project, workspace), act())[1])

    def anyone(request, project, ticket_id, act):
        """Agent i člověk; `act(by)` dostane původce do záznamu (`human` / `agent:<jméno>`). Bez `ticket_id` se
        prostor ticketu nekontroluje (nasazení)."""
        return answer(lambda: act(origin(service, request, project, ticket_id)))

    @router.get("/board")
    def board_state(request: Request, project: str = "", workspace: str = "main", group: str = "branch",
                    snapshot: str = ""):
        """`?group=plan&snapshot=<id>` = týž snímek seskupený podle plánu bez nového čtení (L7d)."""
        return human(request, project, lambda: board.grouped(service, project, workspace, root, group,
                                                             snapshot or None), workspace)

    @router.get("/board.txt")
    def board_text_get(request: Request, project: str = "", workspace: str = "main", mine: int = 0,
                       all: int = 0):  # `?all=1` vypíše i uzavřené řádky celé
        def act():
            by = origin(service, request, project)
            _check(service, project, workspace)
            if mine and not by.startswith("agent:"):
                raise GateError(422, "invalid_payload", "mine=1 patří agentovi.", "Pošlete X-Opora-Actor: agent; name=…")
            found, events, after = board.grouped(service, project, workspace, root), [], 0
            while True:  # deník po stránkách podle id; text ukáže posledních 20
                page = journal.read(service, project, after, journal.LIMIT)
                events += page["events"]
                if len(page["events"]) < journal.LIMIT:
                    break
                after = page["lastId"]
            asked = requests.listing(service, project, True)
            text = board_text.render(found, mine=by.split(":", 1)[1] if mine else None, journal=events,
                                     open_requests=len(asked), all=bool(all))
            return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
        return answer(act)

    @router.post("/rows")
    def row_add(request: Request, body: LinieRowIn, project: str = ""):
        return human(request, project, lambda: rows.add(service.root, project, body.name, body.type, body.base,
                                                        body.target))

    @router.patch("/rows/{row_id}")
    def row_patch(request: Request, row_id: str, body: LinieRowPatch, project: str = ""):
        return human(request, project, lambda: rows.patch(service.root, project, row_id,
                                                          body.model_dump(exclude_unset=True)))

    @router.delete("/rows/{row_id}")
    def row_remove(request: Request, row_id: str, project: str = ""):
        return human(request, project, lambda: rows.remove(service.root, project, row_id,
                                                           work.used_rows(service, project)))

    @router.post("/work")
    def work_create(request: Request, body: LinieWorkIn, project: str = "", workspace: str = "main"):
        fields = body.model_dump(exclude={"idempotencyKey"})
        return human(request, project, lambda: idempotency.once(
            service, project, "work", body.idempotencyKey, {**fields, "workspace": workspace},
            lambda ident: work.create(service, project, workspace, {key: fields[key] for key in BODY}, fields,
                                      tokens.stamp(), root=root, ticket_id=ident and "tk_" + ident)), workspace)

    @router.post("/work/{ticket_id}/attach")
    def work_attach(request: Request, ticket_id: str, body: LinieAttachIn, project: str = ""):
        return human(request, project, lambda: work.attach(service, project, ticket_id, body.model_dump(),
                                                           tokens.stamp(), root=root))

    @router.get("/work/{ticket_id}")
    def work_get(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.get(service, project, ticket_id))

    @router.get("/commit/{sha}")
    def commit_get(request: Request, sha: str, project: str = "", workspace: str = "main"):
        """Detail commitu: plán, karta, kancelář, PR a náhled (docs/navrhy/2026-11-06-linie-detail-commitu.md)."""
        return answer(lambda: (_check(service, project, workspace),
                               commit.detail(service, project, workspace, root, sha, pletor.folder))[1])

    @router.get("/trace/{mark}")
    def trace_get(request: Request, mark: str, project: str = "", workspace: str = "main"):
        """Celá cesta práce podle vodotisku (docs/navrhy/2026-11-06-linie-vodotisk-cesty.md)."""
        return answer(lambda: (_check(service, project, workspace),
                               trace.trace(service, project, workspace, root, mark, pletor.folder))[1])

    @router.post("/work/{ticket_id}/run")
    def work_run(request: Request, ticket_id: str, body: LinieRunIn, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.run(service, project, ticket_id, body.model_dump(),
                                                                       tokens.stamp()))

    @router.post("/work/{ticket_id}/report")
    def work_report(request: Request, ticket_id: str, body: LinieReportIn, project: str = ""):
        checks = [check.model_dump() for check in body.checks]

        def act(by):
            shown = work.report(service, project, ticket_id, body.sha, checks, body.worktree, tokens.stamp(), by,
                                body.tryout and body.tryout.model_dump())
            shown = attempt.publish(service, project, ticket_id, tokens.stamp()) or shown
            requests.follow(service, project, shown, "commit", by, tokens.stamp(), sha=shown["work"]["headSha"])
            return shown
        return anyone(request, project, ticket_id, act)

    @router.post("/work/{ticket_id}/attempt")
    def work_attempt(request: Request, ticket_id: str, body: LinieAttemptIn, project: str = ""):
        payload = body.model_dump(exclude={"idempotencyKey"})

        def act(by):
            shown = idempotency.once(service, project, "attempt", body.idempotencyKey, {**payload, "ticket": ticket_id},
                                     lambda ident: attempt.attempt(service, project, ticket_id, payload, by,
                                                                   tokens.stamp(), ident and "at_" + ident))
            made = next(a for a in shown["work"]["attempts"] if a["branch"] == body.branch)
            requests.follow(service, project, shown, "attempt", by, tokens.stamp(), attemptId=made["attemptId"])
            return shown
        return anyone(request, project, ticket_id, act)

    @router.post("/work/{ticket_id}/revert")
    def work_revert(request: Request, ticket_id: str, body: LinieRevertIn, project: str = ""):
        def act(by):
            if body.op:  # expectedHead mimo digest: opakování po 409 head_moved s opravenou hlavou je týž revert
                idempotency.claim(service.root, project, "revert", body.op, {"ticket": ticket_id, "sha": body.sha})
            return revert.revert(service, project, ticket_id, body.sha, body.expectedHead, tokens.stamp(),
                                 op=body.op, by=by)
        return anyone(request, project, ticket_id, act)

    @router.post("/work/{ticket_id}/rebase-note")
    def work_rebase_note(request: Request, ticket_id: str, body: LinieRebaseNoteIn, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: revert.rebase_note(
            service, project, ticket_id, body.old, body.to, by, tokens.stamp()))

    @router.get("/journal")
    def journal_get(request: Request, project: str = "", workspace: str = "main", after: int = 0, limit: int = 100):
        """Deník Linie: události `linie.*` po `after` v pořadí `id` a `lastId` (L7 §7 bod 5)."""
        return answer(lambda: (_check(service, project, workspace), journal.read(service, project, after, limit))[1])

    @router.post("/work/{ticket_id}/preview")
    def work_preview(request: Request, ticket_id: str, body: LinieWorkPreviewIn | None = None, project: str = ""):
        def act():
            shown = work.get(service, project, ticket_id)
            work.require(shown, "preview")
            branch = shown["work"]["branch"]
            record = previews.start(pletor.folder, root, branch, project, service.root, tokens.stamp(),
                                    fresh=bool(body and body.fresh))
            return work.set_preview(service, project, ticket_id, record, tokens.stamp())
        return human(request, project, act)

    @router.post("/work/{ticket_id}/tried")
    def work_tried(request: Request, ticket_id: str, project: str = ""):
        """Člověk otevřel běžící náhled (zkouška hlavy); bez běžícího náhledu 409 `preview_not_running`."""
        return human(request, project, lambda: work.mark_tried(service, project, ticket_id, tokens.stamp()))

    @router.post("/work/{ticket_id}/accept")
    def work_accept(request: Request, ticket_id: str, body: LinieAcceptIn, project: str = ""):
        return human(request, project, lambda: work.accept(service, project, ticket_id, body.sha, body.note,
                                                           tokens.stamp(), body.untested))

    @router.delete("/work/{ticket_id}/accept")
    def work_revoke(request: Request, ticket_id: str, project: str = ""):
        return human(request, project, lambda: work.revoke_accept(service, project, ticket_id, tokens.stamp()))

    @router.post("/work/{ticket_id}/allow-merge")
    def work_allow(request: Request, ticket_id: str, body: LinieAllowIn, project: str = ""):
        return human(request, project, lambda: work.allow_merge(service, project, ticket_id, body.target,
                                                                tokens.stamp()))

    @router.post("/work/{ticket_id}/accept-merge")
    def work_accept_merge(request: Request, ticket_id: str, body: LinieAcceptMergeIn, project: str = ""):
        return human(request, project, lambda: human_queue.accept_merge(service, project, ticket_id, body.sha, body.op,
                                                                        body.note, tokens.stamp(), body.untested))

    @router.post("/work/{ticket_id}/merge")
    def work_merge(request: Request, ticket_id: str, body: LinieMergeIn | None = None, project: str = ""):
        def act(by):
            shown = work.get(service, project, ticket_id)
            # začleněné (i podle merge logu) vrací merge.py idempotentně beze změny
            if not shown["work"].get("merged") and shown["axes"]["integration"]["state"] == "none":
                work.require(shown, "merge")
            if body and body.op:  # stejné op jen pro týž úkol (jinak 409 idempotency_conflict)
                idempotency.claim(service.root, project, "merge", body.op, {"ticket": ticket_id})
            return merge.merge(service, project, ticket_id, tokens.stamp(), op=body.op if body else None, by=by)
        return anyone(request, project, ticket_id, act)

    @router.post("/work/{ticket_id}/abandon")
    def work_abandon(request: Request, ticket_id: str, body: LinieAbandonIn, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.abandon(service, project, ticket_id, body.sha,
                                                                           body.why, tokens.stamp(), by))

    @router.post("/deploy")
    def deploy_record(request: Request, body: LinieDeployIn, project: str = ""):
        def act(by):
            if body.repo is not None and Path(body.repo).resolve() != Path(root).resolve():
                raise GateError(422, "invalid_payload", "repo je repozitář služby (nebo chybí).", "repo vynechte.")
            full = work.rev(root, body.sha) if work.SHA.fullmatch(body.sha) else None
            if not full:
                raise GateError(422, "invalid_payload", f"Revize {body.sha} v repozitáři neexistuje.",
                                "Pošlete sha nasazeného commitu.")
            done = deploy.record(service.root, project, Path(root) / "opora.local.toml", body.env, full, root, by,
                                 tokens.stamp())
            journal.record(service, project, "linie.deploy", by, {"env": body.env, "sha": full})
            return done
        return anyone(request, project, None, act)

    @router.post("/work/{ticket_id}/block")
    def work_block(request: Request, ticket_id: str, body: LinieBlockIn, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.block(service, project, ticket_id, body.reason,
                                                                         tokens.stamp(), by))

    @router.post("/work/{ticket_id}/defer")
    def work_defer(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.defer(service, project, ticket_id, tokens.stamp(),
                                                                         by))

    @router.post("/work/{ticket_id}/forget")
    def work_forget(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.forget(service, project, ticket_id,
                                                                          tokens.stamp(), by))

    @router.post("/work/{ticket_id}/unblock")
    def work_unblock(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.unblock(service, project, ticket_id,
                                                                           tokens.stamp(), by))

    @router.post("/work/{ticket_id}/resume")
    def work_resume(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.resume(service, project, ticket_id, tokens.stamp(),
                                                                          by))

    return router
