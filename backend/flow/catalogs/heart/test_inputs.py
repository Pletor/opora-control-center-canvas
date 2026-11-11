"""Co srdce budí u ticketu práce: otázka dělníka, odevzdání a selhání (`ticket.failed` → `workFailed`) ano, nápad ne."""
from backend.brain_opora.determinism.test_ticket import ISSUE, heart, send, worker
from backend.canvas.canvas_service import CanvasService
from backend.flow.catalogs.heart.inputs import resolve, trigger_workspaces, wake_input
from database.repositories import opora_events
from database.repositories.tickets import TicketStore


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


def test_failed_work_ticket_wakes_the_heart_with_its_body_and_reason(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        tid = send(service, heart(service), "ticket.issue", ISSUE)["ticket"]["ticketId"]
        event = {"kind": "ticket.failed", "data": {"ticketId": tid, "status": "failed", "reason": "Exekuce zrušena."}}
        item = wake_input(event)
        assert item == {"type": "workFailed", "ticketId": tid, "reason": "Exekuce zrušena."}
        assert resolve(service, "draft", [item]) == []  # ticket ještě není failed: vypadne
        db = service.db_for("draft")
        with db:
            assert TicketStore(db, "draft").move(tid, "issued", "failed", "t")
        (failed,) = resolve(service, "draft", [item])
        assert failed["status"] == "failed" and failed["reason"] == "Exekuce zrušena."
        assert failed["body"]["essence"] == ISSUE["body"]["essence"] and failed["cardId"] == "hero"
    finally:
        service.close()


def test_merge_done_becomes_a_merged_input_that_resolve_keeps():
    event = {"kind": "merge.done", "nodeId": "n1", "executionId": "ex1", "prNumber": 12,
             "data": {"mergeSha": "abc123", "mergedAt": "2026-10-29T10:00:00Z"}}
    assert wake_input(event) == {"type": "merged", "nodeId": "n1", "executionId": "ex1", "mergeSha": "abc123", "pr": 12}
    local = {"kind": "merge.done", "nodeId": "n1", "executionId": "ex1", "prNumber": None,
             "data": {"source": "local", "commit": "def456", "mergeSha": "def456"}}
    assert wake_input(local)["pr"] is None and wake_input(local)["mergeSha"] == "def456"


def test_canvas_failure_wakes_the_heart():
    event = {"kind": "canvas.failed", "data": {"seq": 7, "canvas": 2, "kind": "intent.failed",
                                               "payload": {"pageId": "landing", "nodeId": "ok", "reason": "chybí"}}}
    assert wake_input(event) == {"type": "canvasFailed", "canvas": 2, "kind": "intent.failed",
                                 "payload": {"pageId": "landing", "nodeId": "ok", "reason": "chybí"}}


def test_office_process_event_of_a_card_reevaluates_its_workspace_and_heart_messages_do_not_wake():
    """Hlídač F2: každá přijatá procesní událost karty z Kanceláře označí prostor k vyhodnocení spouštěčů; vlastní
    zásah srdce (`worker.message`) a signál (`card.signal`) srdce nebudí ani nepřepočítají."""
    events = [{"kind": "tool.use", "source": "office", "nodeId": "a", "workspaceId": "w1"},
              {"kind": "worker.status", "source": "office", "nodeId": None, "workspaceId": "w2"},
              {"kind": "worker.message", "source": "opora", "nodeId": "a", "workspaceId": "w3", "data": {}},
              {"kind": "card.signal", "source": "opora", "nodeId": "a", "workspaceId": "w4", "data": {}}]
    assert trigger_workspaces(events) == {"w1"}
    assert [wake_input(event) for event in events[2:]] == [None, None]
