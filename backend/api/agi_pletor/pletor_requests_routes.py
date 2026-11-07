"""Žádosti srdci (docs/navrhy/2026-11-06-linie-rebrand.md §4a), prefix `/api/pletor/requests`, všude `?project=`.

`POST /` `{text, idempotencyKey}` (člověk i agent) vrátí ihned žádost s krokem `accepted`; stejný klíč a text = tatáž
žádost, jiný text 409 `idempotency_conflict`. `POST /{id}/steps` `{k, evidence}` nebo `{k, failed: true, why}` volá
jen služba / srdce (agent nebo token brány, člověk 403 `agent_only`); důkaz se ověří (`linie/requests.py`).
`GET /?open=1` = fronta „Pletor: N otevřených žádostí“, `GET /{id}` jedna žádost. Pletor tu srdce nevolá; routa je kanál.
"""
from fastapi import APIRouter, Request

from backend.agi_pletor.linie import requests
from backend.api.agi_pletor.linie_work_routes import answer, origin
from backend.api.agi_pletor.models import PletorRequestIn, PletorRequestStepIn
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.gate_payloads import GateError


def create_pletor_requests_router(service):
    router = APIRouter(prefix="/api/pletor/requests", tags=["pletor"])

    @router.post("")
    def request_create(request: Request, body: PletorRequestIn, project: str = ""):
        return answer(lambda: requests.create(service, project, body.text, body.idempotencyKey,
                                              origin(service, request, project), tokens.stamp()))

    @router.get("")
    def request_list(project: str = "", open: int = 0):
        def act():
            _check(service, project, "main")
            found = requests.listing(service, project, bool(open))
            return {"requests": found, "open": sum(map(requests.is_open, found))}
        return answer(act)

    @router.get("/{request_id}")
    def request_get(request_id: str, project: str = ""):
        return answer(lambda: (_check(service, project, "main"), requests.get(service, project, request_id))[1])

    @router.post("/{request_id}/steps")
    def request_step(request: Request, request_id: str, body: PletorRequestStepIn, project: str = ""):
        def act():
            by = origin(service, request, project)
            if not by.startswith("agent:"):
                raise GateError(403, "agent_only", "Krok žádosti potvrzuje jen služba nebo srdce.",
                                "Pošlete X-Opora-Actor: agent; name=<jméno> nebo X-Opora-Gate-Token.")
            return requests.confirm(service, project, request_id, body.k, by, tokens.stamp(), body.evidence,
                                    body.failed, body.why)
        return answer(act)

    return router
