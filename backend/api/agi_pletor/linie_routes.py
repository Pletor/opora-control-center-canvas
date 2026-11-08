"""Routy Linie ve Velínu (docs/navrhy/2026-11-06-velin-git-linie.md §5), prefix `/api/pletor/linie`, jen člověk.

- `GET /?project` → `{main, develop, server, deployed, branches, previews, enforcement}`.
- `GET /graph?project` → `{lanes, active, server, deployed, enforcement}` (git-flow obrázek, `linie/graph.py`).
  Přijetí větví se čte z ticketů projektu (`work.acceptance`); bez `project` není nic přijato.
- `GET /diff?branch&target` → `{commits: [{sha7, title}], stat, files}`.
- `POST /previews {branch, project}` → záznam náhledu (`building`); `DELETE /previews/{slug}` → stop;
  `GET /previews/{slug}/log` → `{build, server}`.
- `POST /deployed {sha}` → `{deployed}`.
Agent dostane 403 na všechno: nasazení zapisuje jen člověk z UI. Editor s kuličkami a přijetí práce jsou
v `linie_work_routes.py`. Logika je v `backend/agi_pletor/linie/`.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agi_pletor.linie import acceptance, branches, gitsnap, graph, previews, work
from backend.agi_pletor.linie.view import linie_view
from backend.api.agi_pletor.models import LinieDeployedIn, LiniePreviewIn
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human
from backend.paths import REPO_ROOT

HUMAN = "Linii ve Velínu řídí jen člověk v UI."
GRAPHS = {}  # (projekt, repozitář) → poslední hotový graf s klíčem (gitsnap.cached)


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

    def accepted(project):
        if not project:
            return {}
        _check(service, project, "main")
        return work.accepted(service, project)

    @router.get("/")
    def state(request: Request, project: str = ""):
        return guarded(request, lambda: linie_view(pletor.folder, root, accepted(project)))

    @router.get("/graph")
    def graph_state(request: Request, project: str = ""):
        def act():
            found = accepted(project)
            running = previews.status(pletor.folder)  # registr náhledů jednou pro souhrn i graf

            def build():
                with gitsnap.scope():  # souhrn větví a reference jednou na požadavek
                    view = linie_view(pletor.folder, root, found, running)
                    data = graph.graph(root, pletor.folder, found, running=running)
                for lane in data["lanes"]:  # origin sha pro karty MAIN a DEVELOP
                    summary = view.get(lane["name"])
                    lane["remote"] = summary.get("remote") if isinstance(summary, dict) else None
                return {**data, **{key: view[key] for key in ("server", "deployed", "enforcement")}}

            # opakovaný požadavek bez změny gitu, přijetí, nasazení, náhledů a PR = hotová odpověď bez subprocesu
            key = (gitsnap.state(root), gitsnap.files(acceptance._path(pletor.folder)), found,
                   tuple((r.get("slug"), r.get("state")) for r in running), graph.recent_prs(root))
            return gitsnap.cached(GRAPHS, (project, gitsnap._key(root)), key, build)

        return guarded(request, act)

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

    @router.post("/deployed")
    def deployed(request: Request, body: LinieDeployedIn):
        return guarded(request, lambda: {"deployed": acceptance.set_deployed(pletor.folder, body.sha, _now())})

    return router
