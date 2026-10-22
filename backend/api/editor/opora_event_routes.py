"""Read-only OporaHub events feed: cursor paging and SSE with Last-Event-ID resume (docs/oporahub-events.md)."""
import asyncio
import json
import os
import threading
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.canvas.graph import valid_id
from backend.canvas.opora_change_validation import scope
from backend.canvas.process_signal import PROCESS_SIGNAL
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

    def validate(project, workspace, node):
        scope({"project": project, "workspace": workspace or "draft"})
        if node is not None and not valid_id(node):
            raise ValueError("Neplatné nodeId.")

    def read(project, workspace, since, limit, node=None):
        validate(project, workspace, node)
        with service.reading(project):
            events, oldest, head = store.page(service.db_for(project), project, workspace, since, limit, node)
        cursor = events[-1]["id"] if events else since
        return {"events": events, "cursor": cursor, "head": head or 0,
                # Retention dropped events after `since`: re-read agent-state, then follow from `head`.
                "gap": oldest is not None and since + 1 < oldest}

    @router.get("/events")
    def events(project: str, workspace: str | None = None, since: int = Query(default=0, ge=0),
               limit: int = Query(default=100, ge=1, le=PAGE_LIMIT), nodeId: str | None = None):
        try:
            return read(project, workspace, since, limit, nodeId)
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "events_unavailable"}, status_code=409)

    async def frames(request, project, workspace, cursor, node):
        started, beat = time.monotonic(), time.monotonic()
        with guard:
            streams[0] += 1
        try:
            yield "retry: 2000\n\n"
            while time.monotonic() - started < lifetime:
                if await request.is_disconnected():
                    return
                generation = PROCESS_SIGNAL.generation  # before reading: a write meanwhile wakes at once
                page = await asyncio.to_thread(read, project, workspace, cursor, STREAM_BATCH, node)
                for event in page["events"]:
                    cursor = event["id"]
                    yield f"id: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if time.monotonic() - beat >= heartbeat_seconds:
                    beat = time.monotonic()
                    yield ": heartbeat\n\n"
                if len(page["events"]) < STREAM_BATCH:
                    # Woken by emit_event / process ingest (docs/zivy-proces.md); the poll stays the safety net.
                    await PROCESS_SIGNAL.wait(generation, poll_seconds)
        finally:
            with guard:
                streams[0] -= 1

    @router.get("/events/stream")
    def stream(request: Request, project: str, workspace: str | None = None, since: int | None = Query(default=None, ge=0),
               nodeId: str | None = None):
        try:
            validate(project, workspace, nodeId)
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "events_unavailable"}, status_code=409)
        # Last-Event-ID wins over `since`: a browser EventSource reconnects to the same URL (still carrying
        # the `since` it was opened with) and sends the last id it saw, so the header is the newer cursor.
        resume = request.headers.get("last-event-id")
        cursor = _cursor(resume) if resume is not None or since is None else since
        with guard:
            if streams[0] >= max_streams:  # Bounded: each stream holds a poll loop for up to `lifetime`.
                return JSONResponse({"error": "Too many event streams.", "code": "events_busy"}, status_code=429)
        return StreamingResponse(frames(request, project, workspace, cursor, nodeId), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return router
