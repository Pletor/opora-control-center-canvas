"""Fronta úkolů: zápis, `next` (idempotentní, nejstarší, návrat úkolů prošlých relací), `report` a události `gate.task`."""
import json
from datetime import UTC, datetime, timedelta

import pytest

from backend.brain_opora.determinism import gate, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_payloads import task_body
from backend.canvas.canvas_service import CanvasService
from database.repositories.gate_sessions import GateSessionStore

WORKER = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}
SHA = "ABCDEF1234567"
GREEN = [{"name": "pytest", "status": "green"}]
RED = [{"name": "pytest", "status": "red", "output": "1 failed"}]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def worker(service, now=None):
    """Relace pracovníka; s `now` v minulosti vznikne relace s už prošlým tokenem."""
    issued = gate.tokens.issue_worker(service, "draft", "draft", {"name": "dev"}, now)
    return GateSessionStore(service.db_for("draft")).get(issued["sessionId"])


def create(service, title, node=None):
    payload = {"project": "draft", "workspace": "draft", "title": title, "body": {"do": title}}
    return task_queue.create(service, payload | ({"nodeId": node} if node else {}))


def report(service, session, task_id, checks):
    return task_queue.report(service, session, {"taskId": task_id, "sha": SHA, "summary": "s", "checks": checks})


def task_events(service):
    rows = service.db_for("draft").execute("SELECT data FROM opora_events WHERE kind='gate.task' ORDER BY id").fetchall()
    return [json.loads(row[0])["status"] for row in rows]


def test_task_body_fills_the_fixed_shape_and_refuses_bad_fields():
    assert task_body({"do": "x"}) == {"why": "", "do": "x", "files": [], "doneWhen": [], "dontTouch": [],
                                      "context": {}, "commit": "", "model": "sonnet"}
    for body in ({}, {"do": " "}, {"do": "x", "extra": 1}, {"do": "x", "model": "gpt"}, {"do": "x", "files": "a"},
                 {"do": "x", "dontTouch": [{"path": "a"}]}, {"do": "x", "context": {"who": "?"}}):
        with pytest.raises(GateError):
            task_body(body)
    with pytest.raises(GateError) as clash:
        task_body({"do": "x", "files": ["src/Layout.tsx"], "dontTouch": [{"path": "src/Layout.tsx", "heldBy": "menu"}]})
    assert clash.value.code == "files_held" and "src/Layout.tsx" in str(clash.value)


def test_next_is_idempotent_takes_the_oldest_and_reports_close_tasks(service):
    first, second = create(service, "První", "n1"), create(service, "Druhý")
    session = worker(service)
    got = task_queue.next_task(service, session, {})
    assert got["task"]["id"] == first["taskId"] and got["task"]["body"]["do"] == "První"
    assert task_queue.next_task(service, session, None)["task"]["id"] == first["taskId"]
    assert report(service, session, first["taskId"], GREEN) == {"task": {"id": first["taskId"], "status": "done",
                                                                          "attempts": 0}}
    assert task_queue.next_task(service, session, {})["task"]["id"] == second["taskId"]
    assert report(service, session, second["taskId"], RED)["task"] == {"id": second["taskId"], "status": "ready",
                                                                       "attempts": 1}
    assert task_queue.next_task(service, session, {})["task"]["id"] == second["taskId"]
    assert report(service, session, second["taskId"], GREEN + RED)["task"]["status"] == "failed"
    empty = task_queue.next_task(service, session, {})
    assert empty["task"] is None and isinstance(empty["plan"], list)
    runs = service.db_for("draft").execute("SELECT scope_id, sha, status FROM check_runs ORDER BY recorded_at").fetchall()
    assert [tuple(row) for row in runs] == [("n1", SHA.lower(), "green"), (second["taskId"], SHA.lower(), "red"),
                                            (second["taskId"], SHA.lower(), "green"), (second["taskId"], SHA.lower(), "red")]
    assert task_events(service) == ["ready", "ready", "assigned", "done", "assigned", "assigned", "failed"]


def test_report_refuses_foreign_task_bad_sha_and_no_checks(service):
    task = create(service, "Úkol")
    mine, other = worker(service), worker(service)
    task_queue.next_task(service, mine, {})
    for session, body, code in (
            (other, {"taskId": task["taskId"], "sha": SHA, "summary": "", "checks": GREEN}, "task_not_assigned"),
            (mine, {"taskId": task["taskId"], "sha": "xyz", "summary": "", "checks": GREEN}, "invalid_sha"),
            (mine, {"taskId": task["taskId"], "sha": SHA, "summary": "", "checks": []}, "checks_required"),
            (mine, {"taskId": "ht_none", "sha": SHA, "summary": "", "checks": GREEN}, "task_not_found")):
        with pytest.raises(GateError) as caught:
            task_queue.report(service, session, body)
        assert caught.value.code == code and caught.value.hint
    with pytest.raises(GateError):
        task_queue.next_task(service, mine, {"x": 1})


def test_task_of_an_expired_session_returns_to_ready_on_next(service):
    task = create(service, "Úkol")
    old = worker(service, datetime.now(UTC) - timedelta(hours=9))
    assert task_queue.next_task(service, old, {})["task"]["id"] == task["taskId"]
    fresh = worker(service)
    assert task_queue.next_task(service, fresh, {})["task"]["id"] == task["taskId"]
    assert task_queue.list_tasks(service, "draft", "draft", "assigned")["tasks"][0]["sessionId"] == fresh["id"]


def test_cancel_and_list(service):
    task = create(service, "Úkol")
    assert task_queue.cancel(service, "draft", task["taskId"])["status"] == "cancelled"
    with pytest.raises(GateError) as caught:
        task_queue.cancel(service, "draft", task["taskId"])
    assert caught.value.code == "task_closed"
    assert task_queue.list_tasks(service, "draft", "draft", "ready") == {"tasks": []}
    assert [t["status"] for t in task_queue.list_tasks(service, "draft", "draft")["tasks"]] == ["cancelled"]
    for call in (lambda: task_queue.list_tasks(service, "draft", "draft", "lost"),
                 lambda: task_queue.cancel(service, "nikde", task["taskId"]),
                 lambda: task_queue.create(service, {"project": "draft", "workspace": "draft", "title": "", "body": {}})):
        with pytest.raises(GateError):
            call()
    assert task_events(service) == ["ready", "cancelled"]


def test_heart_writes_ordered_tasks_and_order_is_checked(service):
    payload = {"project": "draft", "workspace": "draft", "title": "Krok", "body": {"do": "x"}}
    later = task_queue.create(service, payload | {"order": 2}, created_by="heart")
    sooner = task_queue.create(service, payload | {"order": 1}, created_by="heart")
    assert (later["createdBy"], later["order"]) == ("heart", 2)
    assert task_queue.next_task(service, worker(service), {})["task"]["id"] == sooner["taskId"]
    assert task_queue.cancel(service, "draft", later["taskId"], by="heart")["status"] == "cancelled"
    actors = service.db_for("draft").execute(
        "SELECT DISTINCT actor_name FROM opora_events WHERE kind='gate.task' AND actor_kind='agent'").fetchall()
    assert {row[0] for row in actors} >= {"heart"}
    for order in (-1, "1", 1.5, True, 10**7):
        with pytest.raises(GateError):
            task_queue.create(service, payload | {"order": order})
    with pytest.raises(ValueError):
        task_queue.create(service, payload, created_by="worker")
