"""agent-state `eventsCursor` and `cards[].lastEventAt`: one snapshot with the outbox, resumable without loss."""
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.opora_event_routes import create_opora_event_router
from backend.api.editor.test_opora_event_routes import frames
from backend.canvas import opora_agent_state_events as outbox
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_events import emit_event
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_events import no_pull_module as no_pull_module  # noqa: PLC0414
from backend.canvas.test_opora_events import planned as planned  # noqa: PLC0414
from backend.canvas.test_opora_executions import claim
from database.repositories import opora_events as store


def read(service):
    return AgentState(service).read(**SCOPE)


def emit(service, node="a", kind="merge.done", workspace="draft"):
    return emit_event(service, project_id="draft", workspace_id=workspace, kind=kind, node_id=node)


def stream(service, cursor, **params):
    app = FastAPI()
    app.include_router(create_opora_event_router(service, poll_seconds=0.01, stream_seconds=0.15))
    with TestClient(app) as client:
        return frames(client.get("/api/oporahub/events/stream", params={**SCOPE, **params},
                                 headers={"Last-Event-ID": str(cursor)}).text)[0]


def test_events_cursor_is_the_outbox_head_and_later_events_follow_it(planned, service):
    claim(planned)
    document = read(service)
    head = store.page(service.db_for("draft"), "draft", None, 0, 1)[2]
    assert document["eventsCursor"] == head > 0
    later = emit(service)
    received = [identifier for identifier, _ in stream(service, document["eventsCursor"])]
    assert received[0] == later and all(identifier > document["eventsCursor"] for identifier in received)


def test_event_written_during_the_read_lands_after_the_cursor(planned, service, monkeypatch):
    """A writer racing the read holds the project lock, so it can only commit after the snapshot."""
    written, original = [], outbox.read

    def racing(db, project, workspace):
        def writer():
            with service.lock_for("draft"):
                written.append(emit(service))
        thread = threading.Thread(target=writer)
        thread.start()
        thread.join(0.2)  # Blocked on the project lock held by the read.
        racing.thread = thread
        return original(db, project, workspace)

    monkeypatch.setattr(outbox, "read", racing)
    document = read(service)
    racing.thread.join()
    assert written and written[0] > document["eventsCursor"]
    assert written[0] in [identifier for identifier, _ in stream(service, document["eventsCursor"])]


def test_last_event_at_is_the_newest_event_of_each_card(planned, service):
    record = claim(planned)
    emit(service, node="a", workspace="other")  # Other workspace never counts.
    newest = store.page(service.db_for("draft"), "draft", "draft", 0, 1000, "a")[0][-1]
    cards = {card["nodeId"]: card for card in read(service)["cards"]}
    assert cards["a"]["lastEventAt"] == newest["at"] and newest["executionId"] in (None, record["executionId"])
    assert all(card["lastEventAt"] is None for node, card in cards.items() if node != "a")


def test_node_filter_on_page_and_stream(planned, service):
    first, other, second = emit(service, "a"), emit(service, "b"), emit(service, "a")
    every = store.page(service.db_for("draft"), "draft", "draft", first - 1, 1000)[0]
    lane = {node: [item["id"] for item in every if item["nodeId"] == node] for node in ("a", "b")}
    assert first in lane["a"] and second in lane["a"] and lane["b"][0] == other  # Derived stage events join a lane.
    app = FastAPI()
    app.include_router(create_opora_event_router(service))
    with TestClient(app) as client:
        page = client.get("/api/oporahub/events", params={**SCOPE, "since": first - 1, "nodeId": "a"}).json()
        assert [item["id"] for item in page["events"]] == lane["a"] and page["head"] >= second
        bad = client.get("/api/oporahub/events", params={**SCOPE, "nodeId": "../x"})
        assert bad.status_code == 409 and bad.json()["code"] == "events_unavailable"
        assert client.get("/api/oporahub/events/stream", params={**SCOPE, "nodeId": "a b"}).status_code == 409
    assert [identifier for identifier, _ in stream(service, first - 1, nodeId="b")] == lane["b"]


def test_read_with_events_stays_write_free(planned, service):
    claim(planned)
    db, sql = service.db_for("draft"), []
    db.set_trace_callback(sql.append)
    try:
        read(service)
    finally:
        db.set_trace_callback(None)
    assert any("opora_events" in command for command in sql)
    assert not any(command.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "CREATE"))
                   for command in sql)
