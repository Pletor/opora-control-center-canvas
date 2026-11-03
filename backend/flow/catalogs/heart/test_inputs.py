"""Co srdce budí: selhaný úkol ano, vrácení úkolu pracovníkem (`release`, status ready s důvodem) ne; u ticketu
práce otázka dělníka a odevzdání ano, nápad ne."""
from backend.brain_opora.determinism.test_ticket import ISSUE, heart, send, worker
from backend.canvas.canvas_service import CanvasService
from backend.flow.catalogs.heart.inputs import resolve, wake_input
from database.repositories import opora_events


def _wakes(service):
    events, _, _ = opora_events.page(service.db_for("draft"), "draft", None, 0, 500)
    return [item for item in map(wake_input, events) if item]


def test_worker_question_and_delivery_of_a_work_ticket_wake_the_heart_with_their_text(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        office = worker(service)
        tid = send(service, heart(service), "ticket.issue", ISSUE)["ticket"]["ticketId"]
        send(service, office, "ticket.claim", {"ticketId": tid})
        send(service, office, "ticket.feedback", {"ticketId": tid, "kind": "idea", "text": "Přidat video."})
        asked = send(service, office, "ticket.feedback", {"ticketId": tid, "kind": "question", "text": "Smím?"})
        items = _wakes(service)
        assert [item["type"] for item in items] == ["workQuestion"]  # nápad ani vydání srdcem nebudí
        question = resolve(service, "draft", items)[0]
        assert question["ticketId"] == tid and question["text"] == "Smím?" and question["status"] == "needs_answer"
        assert question["feedbackId"] == asked["feedback"]["feedbackId"] and question["cardId"] == "hero"
        send(service, heart(service), "ticket.answer", {"ticketId": tid, "feedbackId": question["feedbackId"],
                                                        "text": "Ano."})
        assert resolve(service, "draft", items) == []  # zodpovězená otázka vypadne
        send(service, office, "ticket.deliver", {"ticketId": tid, "summary": "Hotovo.", "sha": "abc1234"})
        delivered = resolve(service, "draft", [item for item in _wakes(service) if item["type"] == "workDelivered"])
        assert [(item["status"], item["delivery"]["summary"]) for item in delivered] == [("delivered", "Hotovo.")]
    finally:
        service.close()


def test_failed_task_wakes_the_heart_but_a_released_one_does_not():
    failed = {"kind": "gate.task", "data": {"taskId": "ht_1", "status": "failed"}}
    released = {"kind": "gate.task", "data": {"taskId": "ht_1", "status": "ready", "reason": "Nestihnu to."}}
    assert wake_input(failed) == {"type": "taskFailed", "taskId": "ht_1"}
    assert wake_input(released) is None


def test_merge_done_becomes_a_merged_input_that_resolve_keeps():
    event = {"kind": "merge.done", "nodeId": "n1", "executionId": "ex1", "prNumber": 12,
             "data": {"mergeSha": "abc123", "mergedAt": "2026-10-29T10:00:00Z"}}
    assert wake_input(event) == {"type": "merged", "nodeId": "n1", "executionId": "ex1", "mergeSha": "abc123", "pr": 12}
    local = {"kind": "merge.done", "nodeId": "n1", "executionId": "ex1", "prNumber": None,
             "data": {"source": "local", "commit": "def456", "mergeSha": "def456"}}
    assert wake_input(local)["pr"] is None and wake_input(local)["mergeSha"] == "def456"
