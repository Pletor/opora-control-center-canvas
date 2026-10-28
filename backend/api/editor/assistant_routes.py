"""Rozhraní asistenta: chat s Claude Code v aplikaci (docs/asistent.md §8, fáze 1 a 2).

Tenký router nad `backend.claude_code.assistant.manager`. Všechny cesty jsou jen pro loopback
(`backend/app/remote_access.py`). Události jdou jako SSE a po výpadku se navážou od `after`.
`POST /approvals/{approvalId}` je rozhodnutí člověka o zápisu na plátno (§5.1).
Klíče Jev (`typesafe`, `celeris`) a povolení externí kontroly bran Schránky pro projekt
(`/jev-gate-check`, docs/schranka-neurony.md §7, §9 bod 10) jsou nastavení aplikace; povolení dává jen člověk.
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.canvas.activity_log import require_authority, require_human
from backend.claude_code.assistant.instructions import default_assistant_instructions
from backend.claude_code.assistant.manager import AssistantError, SessionNotFound
from backend.integrations.typesafe_client import DEFAULT_PROVIDER, PROVIDERS

CREATE_KEYS = {"project", "workspace", "title", "model", "nodeId", "sectorId"}
MESSAGE_KEYS = {"text", "context"}
APPROVAL_KEYS = {"decision", "note"}


def _error(exc):
    return JSONResponse({"error": str(exc)}, status_code=exc.status)


def _body(payload, allowed, required):
    if not isinstance(payload, dict) or set(payload) - allowed or not required <= set(payload):
        raise ValueError("Neplatné tělo požadavku asistenta.")
    return payload


def _cursor(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def sse_frame(event):
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event['seq']}\nevent: message\ndata: {data}\n\n"


async def sse_events(manager, session_id, after, is_disconnected, *, heartbeat=15.0, poll=0.25):
    """Async generátor: polluje buffer přes `asyncio.sleep`, takže neblokuje event loop."""
    cursor, last_beat = after, time.monotonic()
    while True:
        if await is_disconnected():
            return
        try:
            events, closed = manager.events(session_id, cursor)
        except SessionNotFound:
            return
        for event in events:
            cursor = event["seq"]
            yield sse_frame(event)
        if closed:
            return
        if time.monotonic() - last_beat >= heartbeat:
            last_beat = time.monotonic()
            yield ": ping\n\n"
        await asyncio.sleep(poll)


def create_assistant_router(manager, *, heartbeat_seconds=15.0, poll_seconds=0.25, jev_settings=None,
                            jev_provider=DEFAULT_PROVIDER):
    """`jev_settings` je úložiště klíčů Jev (`AppSettings`, §13.2); bez něj Jev nejde zapnout.
    `jev_provider` je poskytovatel zvolený v `opora.local.toml`; `configured` platí pro něj."""
    router = APIRouter(prefix="/api/assistant", tags=["assistant"])

    def _jev():
        keys = {name: bool(jev_settings and jev_settings.jev_key(name)) for name in PROVIDERS}
        return {"configured": keys[jev_provider], "provider": jev_provider, "keys": keys}

    @router.get("/status")
    def status():
        return {**manager.status(), "jev": _jev()}

    def _instructions():
        current = jev_settings.assistant_instructions()
        return {**current, "defaultText": default_assistant_instructions()}

    @router.get("/instructions")
    def instructions_get():
        """Pokyny asistenta (§14.1): uložené, jinak výchozí; platí pro nově spuštěný proces."""
        if jev_settings is None:
            return JSONResponse({"error": "Nastavení aplikace není dostupné."}, status_code=422)
        return _instructions()

    @router.post("/instructions")
    def instructions_set(payload: dict):
        """Uloží pokyny, nebo s `text: null` obnoví výchozí."""
        if jev_settings is None or not isinstance(payload, dict) or set(payload) != {"text"}:
            return JSONResponse({"error": "Tělo je přesně {text: text | null}."}, status_code=422)
        try:
            jev_settings.set_assistant_instructions(payload["text"])
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return _instructions()

    @router.post("/jev-key")
    def jev_key(payload: dict, request: Request):
        """Uloží nebo smaže klíč poskytovatele Jev pro celou aplikaci; klíč se nikdy nevrací.
        Bez `provider` jde o klíč TypeSafe (zpětná kompatibilita)."""
        # Výjimka §4 (docs/plna-autonomie-agenta.md): klíče a tajemství jen člověk, i při plné autonomii.
        require_human(getattr(request.state, "actor", "unknown"), "Klíč poskytovatele ukládá jen člověk v UI.")
        if (jev_settings is None or not isinstance(payload, dict) or "key" not in payload
                or set(payload) - {"key", "provider"}):
            return JSONResponse({"error": "Tělo je {key: text | null, provider?: typesafe | celeris}."}, status_code=422)
        provider = payload.get("provider", "typesafe")
        if provider not in PROVIDERS:
            return JSONResponse({"error": "provider musí být " + " nebo ".join(PROVIDERS) + "."}, status_code=422)
        try:
            jev_settings.set_jev_key(payload["key"], provider)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return {"jev": _jev()}

    @router.get("/jev-gate-check")
    def jev_gate_check_status(project: str):
        """Pro který poskytovatel je v projektu povolená externí kontrola bran (§9 bod 10)."""
        allowed = (jev_settings.gate_check_permissions().get(project, []) if jev_settings else [])
        return {"project": project, "allowed": {name: name in allowed for name in PROVIDERS}}

    @router.post("/jev-gate-check")
    def jev_gate_check_set(payload: dict, request: Request):
        """Povolí nebo zakáže kontrolu bran pro (projekt, poskytovatel); jen člověk v UI."""
        require_authority(getattr(request.state, "actor", "unknown"),
                          "Externí kontrolu bran povoluje jen člověk v UI.")
        if (jev_settings is None or not isinstance(payload, dict)
                or set(payload) != {"project", "provider", "allowed"}):
            return JSONResponse({"error": "Tělo je přesně {project, provider, allowed: true | false}."}, status_code=422)
        try:
            allowed = jev_settings.set_gate_check_allowed(payload["project"], payload["provider"], payload["allowed"])
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return {"project": payload["project"], "allowed": {name: name in allowed for name in PROVIDERS}}

    @router.get("/sessions")
    def sessions(project: str):
        return {"sessions": manager.sessions(project)}

    @router.post("/sessions", status_code=201)
    def create(payload: dict):
        body = _body(payload, CREATE_KEYS, {"project"})
        sector_id = body.get("sectorId")
        if sector_id is not None and (not isinstance(sector_id, str) or len(sector_id) > 128):
            return JSONResponse({"error": "sectorId musí být řetězec do 128 znaků nebo null."}, status_code=400)
        try:
            session = manager.create(body["project"], body.get("workspace"), body.get("title"), body.get("model"), body.get("nodeId"), sector_id)
        except AssistantError as exc:
            return _error(exc)
        return {"session": session}

    @router.post("/sessions/{session_id}/messages", status_code=202)
    def message(session_id: str, payload: dict):
        body = _body(payload, MESSAGE_KEYS, {"text"})
        try:
            event = manager.send(session_id, body["text"], body.get("context"))
        except AssistantError as exc:
            return _error(exc)
        return {"accepted": True, "seq": event["seq"]}

    @router.post("/sessions/{session_id}/title")
    def title(session_id: str, payload: dict):
        body = _body(payload, {"title"}, {"title"})
        try:
            return {"session": manager.rename(session_id, body["title"])}
        except AssistantError as exc:
            return _error(exc)

    @router.post("/sessions/{session_id}/stop")
    def stop(session_id: str):
        try:
            return {"session": manager.stop(session_id)}
        except AssistantError as exc:
            return _error(exc)

    @router.post("/sessions/{session_id}/close")
    def close(session_id: str):
        try:
            return {"session": manager.close(session_id)}
        except AssistantError as exc:
            return _error(exc)

    @router.get("/sessions/{session_id}/transcript")
    def transcript(session_id: str):
        try:
            return {"messages": manager.transcript(session_id)}
        except AssistantError as exc:
            return _error(exc)

    @router.post("/approvals/{approval_id}")
    def approval(approval_id: str, payload: dict):
        """Povolit / zamítnout žádost; neznámá 404, už rozhodnutá 409, špatné tělo 422."""
        if (not isinstance(payload, dict) or set(payload) - APPROVAL_KEYS or "decision" not in payload
                or payload["decision"] not in ("allow", "deny")):
            return JSONResponse({"error": "Tělo je {decision: allow | deny, note?}."}, status_code=422)
        try:
            return manager.decide_approval(approval_id, payload["decision"], payload.get("note"))
        except AssistantError as exc:
            return _error(exc)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

    @router.get("/sessions/{session_id}/events")
    def events(session_id: str, request: Request, after: str | None = None):
        try:
            manager.session(session_id)
        except AssistantError as exc:
            return _error(exc)
        cursor = _cursor(after if after is not None else request.headers.get("last-event-id"))
        stream = sse_events(manager, session_id, cursor, request.is_disconnected,
                            heartbeat=heartbeat_seconds, poll=poll_seconds)
        return StreamingResponse(stream, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return router
