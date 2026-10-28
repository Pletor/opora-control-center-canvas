"""Strážce zkušenosti: kurzor bez historie, outbox, doručení klíčem role, retry při výpadku OpenVikingu."""
import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.strazci import guard_zkusenost
from backend.canvas.strazci.registry import GuardContext
from backend.integrations.openviking_client import OpenVikingUnavailable
from database.repositories import guard_experience as store
from database.repositories import opora_events as events
from database.repositories.journey_runs import JourneyRunStore

NOW = 1_800_000_000.0


class Memory:
    def __init__(self, fail=False, on=True):
        self.fail, self.on, self.writes = fail, on, []

    def enabled(self):
        return self.on

    def _role_client(self, role):
        memory = self

        class Client:
            def write(self, user, uri, text, tags=None):
                if memory.fail:
                    raise OpenVikingUnavailable("down")
                memory.writes.append({"user": user, "uri": uri, "record": json.loads(text), "tags": tags})
        return Client()


@pytest.fixture
def service(tmp_path, monkeypatch):
    instance = CanvasService(tmp_path / "data")
    monkeypatch.setattr(guard_zkusenost.roles, "role", lambda role: {"id": role} if role == "vyvojar" else None)
    monkeypatch.setattr(guard_zkusenost, "journey_pages", lambda service, project: {("app", "j"): "page-a"})
    db = instance.db_for("draft")
    with db:
        db.execute("INSERT INTO desktop_v3_state VALUES('draft','draft',1,?,'2026-10-28')",
                   (json.dumps({"nodes": {"a": {"agentRole": "vyvojar"}, "page-a": {"agentRole": "vyvojar"}}}),))
    yield instance
    instance.close()


def emit(service, kind, node="a", step=None, execution="x1", pr=None, data=None):
    db = service.db_for("draft")
    with db:
        return events.insert(db, {"at": "2026-10-28T09:00:00.000Z", "projectId": "draft", "workspaceId": "draft",
                                  "kind": kind, "nodeId": node, "executionId": execution, "stepId": step,
                                  "prNumber": pr, "stage": None, "health": None,
                                  "actor": {"kind": "system", "name": None}, "data": data or {}})


def journey(service, ok):
    db = service.db_for("draft")
    record = {"schema": "opora.journey-run/1", "applicationId": "app", "journeyId": "j", "planDigest": "sha256:" + "0" * 64,
              "command": "e2e", "at": "2026-10-28T09:00:00Z", "passed": ok,
              "segments": [{"from": "a", "to": "b", "ok": ok}]}
    with db:
        JourneyRunStore(db, "draft").insert(record, "2026-10-28T09:00:00", "2026-10-28T09:00:00")


def run(service, memory=None, now=NOW):
    if memory is not None:
        service.memory_service = memory
    return guard_zkusenost.run(GuardContext(service, "draft", now))


def test_first_run_sets_cursor_without_history_then_skips(service):
    emit(service, "card.closed")
    assert run(service) == []
    assert store.states(service.db_for("draft"), "draft") == {}
    assert run(service) is None


def test_closed_card_and_journey_are_delivered_under_role_key(service):
    run(service)
    emit(service, "step.failed", step="s1")
    emit(service, "step.done", step="s1", execution="x2")
    emit(service, "merge.done", execution="x2", pr=4, data={"repository": "o/r", "mergeSha": "abc"})
    emit(service, "card.closed", execution=None, data={"by": "human"})
    emit(service, "step.done", node="b", step="s9")  # jiná karta, ne zdroj
    journey(service, False)
    memory = Memory()
    assert run(service, memory) == []
    assert store.states(service.db_for("draft"), "draft") == {"pending": 1, "submitted": 2}
    assert run(service, memory, NOW + 10) == []
    assert run(service, memory, NOW + 20) is None
    merge, closed, path = (item["record"] for item in memory.writes)
    assert {item["user"] for item in memory.writes} == {"vyvojar"} and memory.writes[0]["tags"][1] == "kind=guard-experience"
    assert merge["source"] == "merge.done" and merge["passed"] == ["s1"] and merge["failed"] == []  # jen sloučený běh x2
    assert closed["source"] == "card.closed" and closed["role"] == "vyvojar" and closed["passed"] == ["s1"]
    assert closed["failed"][0]["fixedBy"]["executionId"] == "x2" and closed["evidence"]["pullRequest"]["number"] == 4
    assert path["source"] == "journey.run" and path["card"] == "page-a"


def test_unavailable_openviking_keeps_records_queued_and_retries(service):
    run(service)
    emit(service, "card.closed")
    emit(service, "merge.done", pr=1)
    down = Memory(fail=True)
    assert run(service, down) == []
    assert store.states(service.db_for("draft"), "draft") == {"pending": 1, "retry": 1}
    assert run(service, Memory(on=False), NOW + 1) is None
    up = Memory()
    run(service, up, NOW + 5)
    assert store.states(service.db_for("draft"), "draft") == {"submitted": 2} and len(up.writes) == 2


def test_card_without_registered_role_waits(service):
    run(service)
    emit(service, "card.closed", node="bez-role")
    run(service, Memory())
    assert store.states(service.db_for("draft"), "draft") == {"waiting-role": 1}
