"""Registr pojistek (docs/navrhy/2026-11-13-denik-chyb.md §9). Logika v `backend/app/guards.py`.

- `GET /api/pletor/guards?project=&format=json|text` → `{guards: [{id, protects, mode, origin, default, agent_may_toggle,
  lever, wired, linked?, value?}]}`; čte agent i člověk. Propojené přepínače (strop srdce, brána, autonomie) jen odkazují.
- `PUT /api/pletor/guards/{id}` `{project, mode, reason}` → přepne režim (project '' = celá aplikace). Člověk smí vždy,
  agent jen u `agent_may_toggle` a s neprázdným důvodem; jinak 403 (agent) / 428 (bez dokladu).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.api.agi_pletor.pletor_routes import _check
from backend.app import guards
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import HumanRequired
from backend.flow.catalogs.heart import caps_settings


def line(r):
    state = f"propojený přepínač → {r['linked']}" if r.get("linked") else f"{r['mode']} ({r['origin']})"
    extra = ("" if r["wired"] else " · zatím nenapojeno") + (f" · hodnota {r['value']}" if r.get("value") is not None else "")
    return f"{r['id']}: {state}{extra} · chrání: {r['protects']} · páka: {r['lever']}"


def create_guards_router(service):
    router = APIRouter(prefix="/api/pletor", tags=["pletor"])

    def scoped(project):
        if project:
            _check(service, project, "main")

    @router.get("/guards")
    def read_guards(project: str = "", format: str = "json"):
        try:
            scoped(project)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        rows = guards.read(project)
        for row in rows:
            if row["id"] == "heart_hour_cap":
                try:
                    with service.registry_lock:
                        row["value"] = caps_settings.read(service.db)["per_hour"]
                except Exception:  # noqa: BLE001 – přehled pojistek nesmí spadnout kvůli toku srdce; zůstane odkaz
                    row["value"] = None
        if format == "text":
            return PlainTextResponse("\n".join(map(line, rows)))
        return {"guards": rows}

    @router.put("/guards/{guard}")
    def set_guard(guard: str, body: dict, request: Request):
        project, mode, reason = str(body.get("project") or ""), body.get("mode"), str(body.get("reason") or "").strip()
        actor, name = request.state.actor, request.state.agent
        # Stejné pravidlo jako PUT /api/pletor/heart/caps (require_human), jen s výjimkou agent_may_toggle + důvod.
        if actor != "human" and (actor != "agent" or not guards.CATALOG.get(guard, {}).get("agent_may_toggle")
                                 or not reason):
            raise HumanRequired(actor, f"Pojistku {guard} přepíná člověk v UI; agent jen u agent_may_toggle a s důvodem.")
        try:
            scoped(project)
            guards.set_mode(guard, project, mode, (actor, name if actor == "agent" else None), reason[:300])
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        except ValueError as error:
            return JSONResponse(invalid(str(error), 'Příklad: {"project": "", "mode": "warn", "reason": "…"}').body(),
                                status_code=422)
        return {"guards": guards.read(project)}

    return router
