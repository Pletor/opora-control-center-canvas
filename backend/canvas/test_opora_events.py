"""Events outbox: one event per change in the change's transaction, stage.changed only on change, none on reads."""
import time

import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas import opora_events
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_events import emit_event
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_process_sync import ProcessSync
from backend.canvas.test_opora_changesets import SCOPE, accept, baseline, legacy_save, propose
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_executions import claim, credentials
from database.repositories import opora_events as store


@pytest.fixture(autouse=True)
def no_pull_module():
    pulls.register(None)
    original = pulls.source
    pulls.source = lambda: pulls._override
    yield
    pulls.source = original
    pulls.register(None)


@pytest.fixture
def planned(service):
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    return ExecutionResults(service)


def events(service, since=0):
    return store.page(service.db_for("draft"), "draft", None, since, 1000)[0]


def kinds(service, since=0):
    return [item["kind"] for item in events(service, since)]


def head(service):
    return store.page(service.db_for("draft"), "draft", None, 0, 1)[2] or 0


def test_claim_heartbeat_result_each_emit_once_and_stage_only_on_change(planned, service):
    start = head(service)
    record = claim(planned)
    assert kinds(service, start) == ["lease.claimed", "stage.changed"]
    claimed = events(service, start)
    assert claimed[0]["nodeId"] == "a" and claimed[0]["executionId"] == record["executionId"]
    assert claimed[0]["actor"] == {"kind": "agent", "name": "agent:worker"}
    assert (claimed[1]["stage"], claimed[1]["health"], claimed[1]["data"]["reason"]) == ("work", "ok", "runs_active")
    assert list(claimed[1])[:13] == ["id", "at", "kind", "projectId", "workspaceId", "nodeId", "executionId",
                                     "stepId", "prNumber", "stage", "health", "actor", "data"]
    # Live-process extension (docs/zivy-proces.md) follows the original fields; Opora events derive it from kind.
    assert list(claimed[1])[13:] == ["source", "phase", "state", "title", "detail", "refs", "tool", "externalId",
                                     "schema", "eventId"]
    assert (claimed[0]["source"], claimed[0]["phase"], claimed[0]["state"]) == ("opora", "work", "start")
    mark = head(service)
    claim(planned)  # Replay of the same request: no new fact.
    planned.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
    assert kinds(service, mark) == ["lease.heartbeat"]
    mark = head(service)
    payload = {**credentials(record), "requestId": "r1", "result": {"summary": "done"}}
    planned.submit(record["executionId"], payload)
    planned.submit(record["executionId"], payload)  # Idempotent replay.
    reported = events(service, mark)
    assert [item["kind"] for item in reported] == ["result.reported", "stage.changed"]
    assert reported[1]["stage"] == "review" and reported[1]["data"]["previous"]["stage"] == "work"


def test_pure_reads_emit_nothing(planned, service):
    record = claim(planned)
    planned.submit(record["executionId"], {**credentials(record), "requestId": "r", "result": {"summary": "x"}})
    mark = head(service)
    AgentState(service).read(**SCOPE)
    ProcessSync(service).read(**SCOPE)
    planned.history(**SCOPE)
    planned.receipts(record["executionId"], **SCOPE)
    assert head(service) == mark


def test_expired_lease_is_recorded_when_replaced(planned, service):
    first = claim(planned)
    db = service.db_for("draft")
    with db:
        db.execute("UPDATE card_leases SET expires_at=? WHERE node_id='a'", (time.time() - 1,))
    mark = head(service)
    claim(planned, request="second")
    found = events(service, mark)
    expired = next(item for item in found if item["kind"] == "lease.expired")
    assert expired["executionId"] == first["executionId"] and expired["data"]["replacedBy"] == "agent:worker"
    assert [item["kind"] for item in found].count("lease.claimed") == 1


def test_changesets_emit_proposed_and_accepted_with_decisions(planned, service):
    head_revision = AgentState(service).read(**SCOPE)["heads"]["acceptedHead"]
    mark = head(service)
    proposal = propose(service)
    proposed = events(service, mark)
    assert [item["kind"] for item in proposed] == ["changeset.proposed", "decision.created"]
    assert proposed[0]["data"]["proposalId"] == proposal["id"] and proposed[0]["data"]["nodeIds"] == ["a"]
    assert proposed[0]["actor"] == {"kind": "agent", "name": "Builder"}
    mark = head(service)
    accept(service, proposal, head_revision)
    assert kinds(service, mark)[:2] == ["changeset.accepted", "decision.resolved"]


def test_event_rolls_back_with_its_transaction(service):
    db, mark = service.db_for("draft"), head(service)
    with pytest.raises(RuntimeError), db:
        db.execute("BEGIN IMMEDIATE")
        emit_event(db, project_id="draft", workspace_id="draft", kind="merge.done", data={"x": 1})
        raise RuntimeError("change failed")
    assert head(service) == mark
    identifier = emit_event(service, project_id="draft", workspace_id="draft", kind="formal.result",
                            actor={"kind": "human", "name": "Reviewer"})
    assert identifier > mark and events(service, mark)[0]["actor"] == {"kind": "human", "name": "Reviewer"}
    with pytest.raises(ValueError, match="Unknown"):
        emit_event(service, project_id="draft", workspace_id="draft", kind="stage.guessed")


def test_retention_prunes_old_and_excess_rows(service, monkeypatch):
    monkeypatch.setattr(opora_events, "PRUNE_EVERY", 1)
    monkeypatch.setenv("OPORA_EVENTS_MAX_ROWS", "3")
    for _ in range(6):
        emit_event(service, project_id="draft", workspace_id="draft", kind="merge.done")
    found = events(service)
    assert len(found) == 3 and [item["id"] for item in found] == sorted(item["id"] for item in found)
    db = service.db_for("draft")
    with db:
        db.execute("UPDATE opora_events SET at='2000-01-01T00:00:00.000Z'")
    emit_event(service, project_id="draft", workspace_id="draft", kind="merge.done")
    assert len(events(service)) == 1
