"""Rozhraní asistenta: chat s Claude Code v aplikaci (docs/asistent.md §8, fáze 1 a 2).

Tenký router nad `backend.claude_code.assistant.manager`. Všechny cesty jsou jen pro loopback
(`backend/app/remote_access.py`). Události jdou jako SSE a po výpadku se navážou od `after`.
`POST /approvals/{approvalId}` je rozhodnutí člověka o zápisu na plátno (§5.1).
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.claude_code.assistant.manager import AssistantError, SessionNotFound

CREATE_KEYS = {"project", "workspace", "title", "model"}
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


def create_assistant_router(manager, *, heartbeat_seconds=15.0, poll_seconds=0.25, jev_settings=None):
    """`jev_settings` je úložiště klíče TypeSafe Jev (`AppSettings`, §13.2); bez něj Jev nejde zapnout."""
    router = APIRouter(prefix="/api/assistant", tags=["assistant"])

    @router.get("/status")
    def status():
        configured = bool(jev_settings and jev_settings.typesafe_key())
        return {**manager.status(), "jev": {"configured": configured}}

    @router.post("/jev-key")
    def jev_key(payload: dict):
        """Uloží nebo smaže klíč Jev pro celou aplikaci; klíč se nikdy nevrací."""
        if jev_settings is None or not isinstance(payload, dict) or set(payload) != {"key"}:
            return JSONResponse({"error": "Tělo je přesně {key: text | null}."}, status_code=422)
        try:
            return {"jev": {"configured": jev_settings.set_typesafe_key(payload["key"])}}
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

    @router.get("/sessions")
    def sessions(project: str):
        return {"sessions": manager.sessions(project)}

    @router.post("/sessions", status_code=201)
    def create(payload: dict):
        body = _body(payload, CREATE_KEYS, {"project"})
        try:
            session = manager.create(body["project"], body.get("workspace"), body.get("title"), body.get("model"))
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
