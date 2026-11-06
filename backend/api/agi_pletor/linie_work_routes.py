"""Editor Linie a vynucení workflow (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3), prefix `/api/pletor/linie`.

Všude `?project=`; `GET /board` a `POST /work` navíc `&workspace=`. Jen člověk: board, řádky, `POST /work`, attach,
preview, accept (i DELETE), allow-merge. Agent i člověk: `GET /work/{id}`, report, merge (provádí služba),
block / defer / resume; agent se prokáže `X-Opora-Actor: agent; name=…` nebo tokenem brány `X-Opora-Gate-Token`
(projekt i prostor ticketu musí sedět), bez identity 428. Odmítnutí je JSON `{error, code, hint}`.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agi_pletor.linie import board, commit, merge, previews, rows, work
from backend.api.agi_pletor.models import (
    LinieAcceptIn,
    LinieAllowIn,
    LinieAttachIn,
    LinieBlockIn,
    LinieReportIn,
    LinieRowIn,
    LinieRowPatch,
    LinieWorkIn,
)
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import require_human
from backend.paths import REPO_ROOT

HUMAN = "Tento krok Linie dělá jen člověk v UI."
BODY = ("essence", "build", "doneCriteria")


def create_linie_work_router(service, pletor, root=None):
    router = APIRouter(prefix="/api/pletor/linie", tags=["pletor"])
    root = root or REPO_ROOT  # čteno až tady, ať test může podvrhnout repozitář

    def answer(act):
        try:
            return act()
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    def human(request, project, act, workspace="main"):
        require_human(request.state.actor, HUMAN)
        return answer(lambda: (_check(service, project, workspace), act())[1])

    def anyone(request, project, ticket_id, act):
        """Agent i člověk; `act(by)` dostane původce do záznamu (`human` / `agent:<jméno>`)."""
        def checked():
            _check(service, project, "main")
            token = request.headers.get(tokens.HEADER)
            if token:
                session = gate.authenticate(service, token, project, ("worker", "heart"))
                if (work.get(service, project, ticket_id)["workspaceId"] != session["workspace_id"]
                        and session.get("role") != "heart"):
                    raise GateError(403, "gate_scope", "Ticket patří jinému pracovnímu prostoru.",
                                    "Pracujte jen s tickety svého prostoru.")
                return act("agent:" + (session.get("worker_name") or session.get("role") or "?"))
            if request.state.actor == "human":
                return act("human")
            if request.state.actor == "agent":
                return act("agent:" + (getattr(request.state, "agent", None) or "?"))
            raise GateError(428, "identity_required", "Chybí identita původce.",
                            "Pošlete X-Opora-Actor: agent; name=<jméno> nebo X-Opora-Gate-Token.")
        return answer(checked)

    @router.get("/board")
    def board_state(request: Request, project: str = "", workspace: str = "main"):
        return human(request, project, lambda: board.board(service, project, workspace, root), workspace)

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
        fields = body.model_dump()
        return human(request, project, lambda: work.create(service, project, workspace,
                                                           {key: fields[key] for key in BODY}, fields,
                                                           tokens.stamp(), root=root), workspace)

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

    @router.post("/work/{ticket_id}/report")
    def work_report(request: Request, ticket_id: str, body: LinieReportIn, project: str = ""):
        checks = [check.model_dump() for check in body.checks]
        return anyone(request, project, ticket_id, lambda by: work.report(
            service, project, ticket_id, body.sha, checks, body.worktree, tokens.stamp(), by))

    @router.post("/work/{ticket_id}/preview")
    def work_preview(request: Request, ticket_id: str, project: str = ""):
        def act():
            branch = work.get(service, project, ticket_id)["work"]["branch"]
            record = previews.start(pletor.folder, root, branch, project, service.root, tokens.stamp())
            return work.set_preview(service, project, ticket_id, record, tokens.stamp())
        return human(request, project, act)

    @router.post("/work/{ticket_id}/accept")
    def work_accept(request: Request, ticket_id: str, body: LinieAcceptIn, project: str = ""):
        return human(request, project, lambda: work.accept(service, project, ticket_id, body.sha, body.note,
                                                           tokens.stamp()))

    @router.delete("/work/{ticket_id}/accept")
    def work_revoke(request: Request, ticket_id: str, project: str = ""):
        return human(request, project, lambda: work.revoke_accept(service, project, ticket_id, tokens.stamp()))

    @router.post("/work/{ticket_id}/allow-merge")
    def work_allow(request: Request, ticket_id: str, body: LinieAllowIn, project: str = ""):
        return human(request, project, lambda: work.allow_merge(service, project, ticket_id, body.target,
                                                                tokens.stamp()))

    @router.post("/work/{ticket_id}/merge")
    def work_merge(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: merge.merge(service, project, ticket_id, tokens.stamp()))

    @router.post("/work/{ticket_id}/block")
    def work_block(request: Request, ticket_id: str, body: LinieBlockIn, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.block(service, project, ticket_id, body.reason,
                                                                         tokens.stamp()))

    @router.post("/work/{ticket_id}/defer")
    def work_defer(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.defer(service, project, ticket_id, tokens.stamp()))

    @router.post("/work/{ticket_id}/resume")
    def work_resume(request: Request, ticket_id: str, project: str = ""):
        return anyone(request, project, ticket_id, lambda by: work.resume(service, project, ticket_id, tokens.stamp()))

    return router
