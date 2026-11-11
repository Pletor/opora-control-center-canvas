"""Plán stránky na plátně 2 (`docs/navrhy/2026-11-10-platno-2.md`, verze 3): layout, stav boxu a sken přes REA.

Logika je v `backend/project/architecture/page_plan.py` a `page_plan_scan.py`. Člověk = relace UI, agent = token
brány (worker / heart, prostor tokenu) nebo `X-Opora-Actor: agent`; bez identity 428 `identity_required`.
Odmítnutí routy je JSON `{error, code, hint}`; tvar sekcí 422 `InvalidPayload`, uložení grafu 409 `{error}`,
stav boxu a zahození skenu od agenta 403 `{error, humanRequired}`. `/{id}/build-plan` (F3) vrací
přírůstek plátna 3 a id nepřijatého návrhu grafu srdce (`backend/canvas/plan_from_page.py`). Sken je jen z tohoto počítače (`remote_access.py`);
`/scan/latest` je registrovaná před `/scan/{scan_id}`, jinak by ji pohltila.
"""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas import plan_from_page
from backend.canvas.activity_log import require_human
from backend.project.architecture import page_plan, page_plan_scan


def identity(service, request, project, workspace):
    """`human` / `agent`; token pracovníka platí jen pro svůj prostor (srdce pro celý projekt)."""
    token = request.headers.get(tokens.HEADER)
    if token:
        session = gate.authenticate(service, token, project, ("worker", "heart"))
        if workspace != session["workspace_id"] and session.get("role") != "heart":
            raise GateError(403, "gate_scope", "Token platí jen pro svůj pracovní prostor.",
                            "Pracujte v prostoru svého tokenu.")
        return "agent"
    if request.state.actor in ("human", "agent"):
        return request.state.actor
    raise GateError(428, "identity_required", "Chybí identita původce.",
                    "Pošlete X-Opora-Gate-Token, nebo X-Opora-Actor: agent; name=<jméno>.")


def answer(act):
    try:
        return act()
    except GateError as error:
        return JSONResponse(error.body(), status_code=error.status)


def _scope(payload):
    return (payload.get("project"), payload.get("workspace")) if isinstance(payload, dict) else (None, None)


def create_page_plan_router(service, scan_runner=None):
    router = APIRouter(prefix="/api/page-plan", tags=["page-plan"])

    @router.get("")
    def read(request: Request, project: str, workspace: str, pageId: str):
        return answer(lambda: (identity(service, request, project, workspace),
                               page_plan.read(service, project, workspace, pageId))[1])

    @router.post("")
    def save(payload: dict, request: Request):
        def act():
            by = identity(service, request, *_scope(payload))
            scan_id = payload.get("scanId")
            scanned = (page_plan_scan.proposal_sections(service, scan_id, *_scope(payload),
                                                        payload.get("pageId")) if scan_id is not None else ())
            saved = page_plan.save(service, payload, by, scanned)
            if scan_id is not None:
                page_plan_scan.mark(service, scan_id, *_scope(payload), "adopted")
            return saved
        return answer(act)

    @router.post("/scan")
    def scan(payload: dict, request: Request):
        def act():
            identity(service, request, *_scope(payload))
            return page_plan_scan.start(service, payload, scan_runner)
        return answer(act)

    @router.get("/scan/latest")
    def scan_latest(request: Request, project: str, workspace: str, pageId: str):
        return answer(lambda: (identity(service, request, project, workspace),
                               page_plan_scan.latest(service, project, workspace, pageId))[1])

    @router.get("/scan/{scan_id}")
    def scan_state(scan_id: str, request: Request, project: str, workspace: str):
        return answer(lambda: (identity(service, request, project, workspace),
                               page_plan_scan.get(service, scan_id, project, workspace))[1])

    @router.get("/scan/{scan_id}/capture/{name}")
    def scan_capture(scan_id: str, name: str, request: Request, project: str, workspace: str):
        return answer(lambda: (identity(service, request, project, workspace), FileResponse(
            page_plan_scan.capture_file(service, scan_id, project, workspace, name), media_type="image/png"))[1])

    @router.post("/scan/{scan_id}/discard")
    def scan_discard(scan_id: str, payload: dict, request: Request):
        require_human(request.state.actor, "Návrh skenu zahazuje jen člověk v UI.")
        return answer(lambda: page_plan_scan.mark(service, scan_id, *_scope(payload), "discarded"))

    @router.post("/{page_id}/build-plan")
    def build_plan(page_id: str, payload: dict, request: Request):
        """Srdce staví plátno 3 ze stránky nebo domény (`page_id`): jen nepřijatý návrh grafu, přijímá člověk."""
        def act():
            identity(service, request, *_scope(payload))
            if set(payload) != {"project", "workspace"}:
                raise GateError(422, "invalid_payload", "Tělo je {project, workspace}.", "pageId je v adrese.")
            return plan_from_page.build(service, payload["project"], payload["workspace"], page_id)
        return answer(act)

    @router.post("/{page_id}/boxes/{section_id}/status")
    def box_status(page_id: str, section_id: str, payload: dict, request: Request):
        require_human(request.state.actor, "Stav boxu (Přijmout / Zahodit) mění jen člověk v UI.")
        return answer(lambda: page_plan.set_status(service, payload, page_id, section_id))

    return router
