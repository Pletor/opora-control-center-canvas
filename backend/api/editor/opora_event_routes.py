"""Read-only OporaHub events feed: cursor paging and SSE with Last-Event-ID resume (docs/oporahub-events.md)."""
import asyncio
import json
import os
import threading
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.canvas.opora_change_validation import scope
from database.repositories import opora_events as store

PAGE_LIMIT = 500
STREAM_BATCH = 200
STREAM_SECONDS = 300.0
MAX_STREAMS = 8


def _cursor(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def create_opora_event_router(service, *, poll_seconds=0.5, heartbeat_seconds=15.0, stream_seconds=None,
                              max_streams=MAX_STREAMS):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    lifetime = stream_seconds if stream_seconds is not None else float(
        os.environ.get("OPORA_EVENTS_STREAM_SECONDS", STREAM_SECONDS))
    streams, guard = [0], threading.Lock()

    def read(project, workspace, since, limit):
        scope({"project": project, "workspace": workspace or "draft"})
        with service.reading(project):
            events, oldest, head = store.page(service.db_for(project), project, workspace, since, limit)
        cursor = events[-1]["id"] if events else since
        return {"events": events, "cursor": cursor, "head": head or 0,
                # Retention dropped events after `since`: re-read agent-state, then follow from `head`.
                "gap": oldest is not None and since + 1 < oldest}

    @router.get("/events")
    def events(project: str, workspace: str | None = None, since: int = Query(default=0, ge=0),
               limit: int = Query(default=100, ge=1, le=PAGE_LIMIT)):
        try:
            return read(project, workspace, since, limit)
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "events_unavailable"}, status_code=409)

    async def frames(request, project, workspace, cursor):
        started, beat = time.monotonic(), time.monotonic()
        with guard:
            streams[0] += 1
        try:
            yield "retry: 2000\n\n"
            while time.monotonic() - started < lifetime:
                if await request.is_disconnected():
                    return
                page = await asyncio.to_thread(read, project, workspace, cursor, STREAM_BATCH)
                for event in page["events"]:
                    cursor = event["id"]
                    yield f"id: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if time.monotonic() - beat >= heartbeat_seconds:
                    beat = time.monotonic()
                    yield ": heartbeat\n\n"
                if len(page["events"]) < STREAM_BATCH:
                    await asyncio.sleep(poll_seconds)
        finally:
            with guard:
                streams[0] -= 1

    @router.get("/events/stream")
    def stream(request: Request, project: str, workspace: str | None = None, since: int | None = Query(default=None, ge=0)):
        try:
            scope({"project": project, "workspace": workspace or "draft"})
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "events_unavailable"}, status_code=409)
        cursor = _cursor(request.headers.get("last-event-id")) if since is None else since
        with guard:
            if streams[0] >= max_streams:  # Bounded: each stream holds a poll loop for up to `lifetime`.
                return JSONResponse({"error": "Too many event streams.", "code": "events_busy"}, status_code=429)
        return StreamingResponse(frames(request, project, workspace, cursor), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return router
