"""Events feed API: cursor paging, retention gap, SSE resume by Last-Event-ID and heartbeat comments."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.opora_event_routes import create_opora_event_router
from backend.app.factory import create_app
from backend.canvas.opora_events import emit_event
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414

PARAMS = {"project": "draft", "workspace": "draft"}


def seed(service, count):
    return [emit_event(service, project_id="draft", workspace_id="draft", kind="merge.done", node_id=None,
                       pr_number=index, data={"n": index}) for index in range(count)]


def frames(text):
    """`[(id, event)]` of data frames and the number of heartbeat comments in an SSE body."""
    result, beats = [], 0
    for block in text.split("\n\n"):
        lines = block.strip().splitlines()
        if lines == [": heartbeat"]:
            beats += 1
        ids = [line[4:] for line in lines if line.startswith("id: ")]
        data = [line[6:] for line in lines if line.startswith("data: ")]
        if ids and data:
            result.append((int(ids[0]), json.loads(data[0])))
    return result, beats


def test_cursor_paging_through_the_factory_app(service):
    ids = seed(service, 5)
    with TestClient(create_app(service.root), base_url="http://127.0.0.1:8740") as client:
        first = client.get("/api/oporahub/events", params={**PARAMS, "limit": 2}).json()
        assert [item["id"] for item in first["events"]] == ids[:2] and first["cursor"] == ids[1]
        assert first["head"] == ids[-1] and first["gap"] is False
        rest = client.get("/api/oporahub/events", params={**PARAMS, "since": first["cursor"], "limit": 10}).json()
        assert [item["id"] for item in rest["events"]] == ids[2:] and rest["cursor"] == ids[-1]
        empty = client.get("/api/oporahub/events", params={**PARAMS, "since": ids[-1]}).json()
        assert empty["events"] == [] and empty["cursor"] == ids[-1]
        assert client.get("/api/oporahub/events", params={"project": "../x"}).status_code == 409
        assert first["events"][0]["data"] == {"n": 0} and first["events"][0]["prNumber"] == 0


def test_gap_after_retention(service):
    ids = seed(service, 3)
    db = service.db_for("draft")
    with db:
        db.execute("DELETE FROM opora_events WHERE id<?", (ids[2],))
    app = FastAPI()
    app.include_router(create_opora_event_router(service))
    with TestClient(app) as client:
        assert client.get("/api/oporahub/events", params={**PARAMS, "since": 0}).json()["gap"] is True
        assert client.get("/api/oporahub/events", params={**PARAMS, "since": ids[1]}).json()["gap"] is False


def test_sse_resumes_after_last_event_id_and_beats(service):
    ids = seed(service, 4)
    app = FastAPI()
    app.include_router(create_opora_event_router(service, poll_seconds=0.01, heartbeat_seconds=0.0,
                                                 stream_seconds=0.2))
    with TestClient(app) as client:
        response = client.get("/api/oporahub/events/stream", params=PARAMS, headers={"Last-Event-ID": str(ids[1])})
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
        received, beats = frames(response.text)
        assert [identifier for identifier, _ in received] == ids[2:] and beats >= 1
        assert all(event["kind"] == "merge.done" for _, event in received)
        again, _ = frames(client.get("/api/oporahub/events/stream", params={**PARAMS, "since": ids[-1]}).text)
        assert again == []


def test_last_event_id_wins_over_since_on_reconnect(service):
    """An EventSource opened with `?since=` reconnects to the same URL with Last-Event-ID: resume after it."""
    ids = seed(service, 4)
    app = FastAPI()
    app.include_router(create_opora_event_router(service, poll_seconds=0.01, heartbeat_seconds=60.0, stream_seconds=0.2))
    with TestClient(app) as client:
        response = client.get("/api/oporahub/events/stream", params={**PARAMS, "since": 0}, headers={"Last-Event-ID": str(ids[2])})
        received, _ = frames(response.text)
        assert [identifier for identifier, _ in received] == ids[3:]


def test_stream_count_is_bounded(service):
    app = FastAPI()
    app.include_router(create_opora_event_router(service, stream_seconds=0.05, max_streams=0))
    with TestClient(app) as client:
        assert client.get("/api/oporahub/events/stream", params=PARAMS).status_code == 429
