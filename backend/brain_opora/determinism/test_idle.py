"""Spouštěč prázdné fronty (OPORA-002): přijatý plán bez karty k převzetí a bez běhu budí srdce jednou na stav."""
import pytest

from backend.brain_opora.determinism import idle
from backend.canvas.canvas_service import CanvasService

NOW = 1_800_000_000.0  # 2027-01-15T08:00:00Z
SINCE = "2027-01-15T07:45:00+00:00"  # 15 min před NOW


def stage(name, count=0, reason="ok", health="ok"):
    return {"id": name, "count": count, "health": health, "reason": reason}


def state(revision="r1", merged=3, claim=0, work=0, evidence=0, review=0, merge_reason="merged", decisions=()):
    return {"heads": {"acceptedHead": revision}, "cardsTotal": 4, "decisions": list(decisions),
            "stages": [stage("claim", claim, "cards_ready" if claim else "nothing_ready"),
                       stage("work", work), stage("evidence", evidence), stage("review", review),
                       stage("merge", merged, merge_reason)],
            "cards": []}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")
    yield canvas
    canvas.close()


def reader(**facts):
    current = {"state": state(), "questions": 0, "since": SINCE, **facts}
    return current, lambda service, project, workspace: (current["state"], current["questions"], current["since"])


def test_empty_frontier_for_ten_minutes_wakes_once_with_counts(service):
    _, read = reader()
    found, reasons = idle.wakes(service, "draft", ["w1"], "at", NOW, read=read)
    assert found == [("w1", {"type": "idle", "reason": "frontier_empty", "since": SINCE, "cardsTotal": 4, "done": 3})]
    assert reasons == {"w1": "frontier_empty"}
    with service.reading("draft"):
        assert service.db_for("draft").execute("SELECT key FROM heart_triggers").fetchone()[0] == "trigger:idle:w1:r1:3"


def test_same_state_does_not_wake_again(service):
    _, read = reader()
    idle.wakes(service, "draft", ["w1"], "at", NOW, read=read)
    found, reasons = idle.wakes(service, "draft", ["w1"], "at", NOW + 600, read=read)
    assert found == [] and reasons == {"w1": "frontier_empty"}


def test_another_merged_card_or_new_plan_revision_wakes_again(service):
    current, read = reader()
    idle.wakes(service, "draft", ["w1"], "at", NOW, read=read)
    current["state"] = state(merged=4)
    assert [item["done"] for _, item in idle.wakes(service, "draft", ["w1"], "at", NOW, read=read)[0]] == [4]
    current["state"] = state(revision="r2", merged=4)
    assert len(idle.wakes(service, "draft", ["w1"], "at", NOW, read=read)[0]) == 1


@pytest.mark.parametrize("busy", [{"claim": 1}, {"work": 1}, {"evidence": 1}, {"review": 1},
                                  {"merge_reason": "pull_requests_open"}, {"revision": None}])
def test_ready_card_active_run_or_office_work_does_not_wake(service, busy):
    _, read = reader(state=state(**busy))
    assert idle.wakes(service, "draft", ["w1"], "at", NOW, read=read) == ([], {"w1": None})


@pytest.mark.parametrize("facts", [{"questions": 1}, {"state": state(decisions=[{"kind": "accept_low"}])}])
def test_open_question_or_decision_for_the_human_waits_for_the_human(service, facts):
    _, read = reader(**facts)
    assert idle.wakes(service, "draft", ["w1"], "at", NOW, read=read) == ([], {"w1": "waiting_human"})


def test_less_than_ten_minutes_or_no_activity_does_not_wake_yet(service):
    _, read = reader(since="2027-01-15T07:51:00+00:00")
    assert idle.wakes(service, "draft", ["w1"], "at", NOW, read=read) == ([], {"w1": "frontier_empty"})
    _, read = reader(since=None)
    assert idle.wakes(service, "draft", ["w1"], "at", NOW, read=read)[0] == []


def test_done_count_falls_back_to_closed_cards_without_the_pull_request_module():
    value = state()
    value["stages"][-1] = stage("merge", 0, "pull_request_link_module_missing", "not_connected")
    value["cards"] = [{"reason": "card_closed"}, {"reason": "plan_written_back"}, {"reason": "card_in_plan"}]
    assert idle.done_count(value) == 2


def test_last_activity_is_the_newest_activity_event_of_the_workspace(service):
    from database.repositories import opora_events

    def event(at, kind, workspace="w1"):
        return {"at": at, "projectId": "draft", "workspaceId": workspace, "kind": kind, "nodeId": None,
                "executionId": None, "stepId": None, "prNumber": None, "stage": None, "health": None,
                "actor": {"kind": "agent", "name": "a"}, "data": {}}

    with service.lock_for("draft"):
        db = service.db_for("draft")
        with db:
            opora_events.insert(db, event("2027-01-15T07:00:00Z", "merge.done"))
            opora_events.insert(db, event("2027-01-15T07:30:00Z", "step.done"))  # krok není činnost fronty
            opora_events.insert(db, event("2027-01-15T07:40:00Z", "merge.done", "w2"))
        assert idle.last_activity(db, "draft", "w1") == "2027-01-15T07:00:00Z"
