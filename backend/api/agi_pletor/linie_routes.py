"""Routy Linie ve Velínu (docs/navrhy/2026-11-06-velin-git-linie.md §5), prefix `/api/pletor/linie`, jen člověk.

- `GET /` → `{main, develop, server, deployed, branches, previews, enforcement}`.
- `GET /diff?branch&target` → `{commits: [{sha7, title}], stat, files}`.
- `POST /previews {branch, project}` → záznam náhledu (`building`); `DELETE /previews/{slug}` → stop;
  `GET /previews/{slug}/log` → `{build, server}`.
- `POST /accept {branch, sha, target, note}`, `DELETE /accept/{branch}` → stav přijetí.
- `POST /deployed {sha}` → stav přijetí s `deployed`.
Agent dostane 403 na všechno: přijetí a nasazení zapisuje jen člověk z UI. Logika je v `backend/agi_pletor/linie/`.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agi_pletor.linie import acceptance, branches, previews
from backend.agi_pletor.linie.view import linie_view
from backend.api.agi_pletor.models import LinieAcceptIn, LinieDeployedIn, LiniePreviewIn
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human
from backend.paths import REPO_ROOT

HUMAN = "Linii ve Velínu řídí jen člověk v UI."


def _now():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_linie_router(service, pletor, root=None):
    router = APIRouter(prefix="/api/pletor/linie", tags=["pletor"])
    root = root or REPO_ROOT  # čteno až tady, ať test může podvrhnout repozitář

    def guarded(request, act):
        require_human(request.state.actor, HUMAN)
        try:
            return act()
        except ValueError as error:
            return JSONResponse(invalid(str(error), "Zkontrolujte větev, cíl a sha.").body(), status_code=422)
        except KeyError:
            gone = GateError(404, "preview_not_found", "Náhled neexistuje.", "Seznam je v GET /api/pletor/linie/.")
            return JSONResponse(gone.body(), status_code=gone.status)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/")
    def state(request: Request):
        return guarded(request, lambda: linie_view(pletor.folder, root))

    @router.get("/diff")
    def diff(request: Request, branch: str = "", target: str = ""):
        return guarded(request, lambda: branches.diff(root, branch, target))

    @router.post("/previews")
    def preview_start(request: Request, body: LiniePreviewIn):
        def act():
            _check(service, body.project, "main")
            return previews.start(pletor.folder, root, body.branch, body.project, service.root, _now())

        return guarded(request, act)

    @router.delete("/previews/{slug}")
    def preview_stop(request: Request, slug: str):
        return guarded(request, lambda: previews.stop(pletor.folder, slug))

    @router.get("/previews/{slug}/log")
    def preview_log(request: Request, slug: str):
        return guarded(request, lambda: previews.log(pletor.folder, slug))

    @router.post("/accept")
    def accept(request: Request, body: LinieAcceptIn):
        return guarded(request, lambda: acceptance.accept(pletor.folder, body.branch, body.sha, body.target,
                                                          body.note, _now()))

    @router.delete("/accept/{branch:path}")
    def revoke(request: Request, branch: str):
        return guarded(request, lambda: acceptance.revoke(pletor.folder, branch))

    @router.post("/deployed")
    def deployed(request: Request, body: LinieDeployedIn):
        return guarded(request, lambda: acceptance.set_deployed(pletor.folder, body.sha, _now()))

    return router
