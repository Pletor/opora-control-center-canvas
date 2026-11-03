"""Ticket navázaný na skutečnou exekuci: claim s executionId, ověřený výsledek, sloučení, zrušení a vrácení."""
import pytest

from backend.brain_opora.determinism import ticket, ticket_lifecycle
from backend.brain_opora.determinism.test_ticket import ISSUE, heart, refused, send, worker
from backend.canvas.opora_execution_pr_closure import merge_events
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE, baseline, service  # noqa: F401
from backend.canvas.test_opora_executions import claim as claim_execution
from backend.canvas.test_opora_executions import credentials
from database.repositories import opora_events

SHA = "a" * 40


@pytest.fixture
def authority(service):  # noqa: F811
    baseline(service)
    return ExecutionResults(service)


def issued(service, card="a"):  # noqa: F811
    return send(service, heart(service), "ticket.issue", {**ISSUE, "cardId": card})["ticket"]["ticketId"]


def status(service, tid):  # noqa: F811
    return ticket.get(service, "draft", tid)["status"]


def report(authority, record, checks):
    result = {"summary": "Hotovo."}
    if checks is not None:
        result["selfChecks"] = {"headSha": SHA, "checks": [
            {"name": name, "command": name, "exitCode": 0 if ok else 1, "status": "passed" if ok else "failed"}
            for name, ok in checks]}
    return authority.submit(record["executionId"], {**credentials(record), "requestId": "r1", "result": result})


def deliver(service, office, tid):  # noqa: F811
    return send(service, office, "ticket.deliver", {"ticketId": tid, "summary": "Hotovo."})["ticket"]["status"]


def merge(service, record):  # noqa: F811
    db = service.db_for("draft")
    with db:
        db.execute("INSERT INTO opora_execution_pull_requests(project_id,workspace_id,execution_id,node_id,"
                   "accepted_revision,repository,number,head_ref,head_sha,state,enrollment,source,linked_by,"
                   "created_at,updated_at) VALUES('draft','draft',?,?,?,'o/r',7,'h',?,'merged','none','github',"
                   "'agent','t','t')", (record["executionId"], record["nodeId"], record["acceptedRevision"], SHA))
        row = {"node_id": record["nodeId"], "execution_id": record["executionId"], "repository": "o/r",
               "number": 7, "source": "github"}
        merge_events(db, "draft", "draft", row, SHA, "2026-11-03T10:00:00Z")


def test_claim_binds_the_running_execution_of_the_ticket_card(service, authority):  # noqa: F811
    office, tid = worker(service), issued(service)
    record = claim_execution(authority)
    wrong = issued(service, card="b")
    assert refused(service, office, "ticket.claim", {"ticketId": wrong, "executionId": record["executionId"]}).code == (
        "ticket_execution")
    assert refused(service, office, "ticket.claim", {"ticketId": tid, "executionId": "nope"}).status == 409
    claimed = send(service, office, "ticket.claim", {"ticketId": tid, "executionId": record["executionId"]})
    assert claimed["ticket"]["machine"]["executionId"] == record["executionId"]
    assert status(service, wrong) == "issued"  # odmítnutý claim ticket nevzal


def test_green_self_checks_verify_and_the_merge_closes(service, authority):  # noqa: F811
    office, tid = worker(service), issued(service)
    record = claim_execution(authority)
    send(service, office, "ticket.claim", {"ticketId": tid, "executionId": record["executionId"]})
    assert deliver(service, office, tid) == "delivered"
    report(authority, record, [("npm test", True), ("npm run build", True)])
    assert status(service, tid) == "verified"
    merge(service, record)
    assert status(service, tid) == "closed"


def test_red_checks_wait_and_an_early_result_is_caught_up_on_deliver(service, authority):  # noqa: F811
    office, tid = worker(service), issued(service)
    record = claim_execution(authority)
    send(service, office, "ticket.claim", {"ticketId": tid, "executionId": record["executionId"]})
    report(authority, record, [("npm test", False)])
    assert status(service, tid) == "claimed"  # výsledek před odevzdáním ticket neposune
    assert deliver(service, office, tid) == "delivered"  # červená kontrola: čeká
    merge(service, record)  # sloučený PR prošel bránou: verified a closed
    assert status(service, tid) == "closed"

    early = issued(service, card="b")
    second = claim_execution(authority, request="second", node="b")
    send(service, office, "ticket.claim", {"ticketId": early, "executionId": second["executionId"]})
    report(authority, second, [("npm test", True)])
    assert deliver(service, office, early) == "verified"


def test_cancelled_execution_fails_the_ticket_and_without_ticket_nothing_happens(service, authority):  # noqa: F811
    office, tid = worker(service), issued(service)
    record = claim_execution(authority)
    send(service, office, "ticket.claim", {"ticketId": tid, "executionId": record["executionId"]})
    db = service.db_for("draft")
    with db:
        db.execute("UPDATE opora_executions SET record=json_set(record,'$.state','cancelled') WHERE id=?",
                   (record["executionId"],))
        assert ticket_lifecycle.safe_follow(db, "draft", record["executionId"]) == "failed"
        assert ticket_lifecycle.safe_follow(db, "draft", "unbound") is None
    events, _, _ = opora_events.page(db, "draft", None, 0, 500)
    (failed,) = [event for event in events if event["kind"] == "ticket.failed"]
    assert failed["data"] == {"ticketId": tid, "status": "failed", "reason": ticket_lifecycle.FAILED_REASON}
    assert failed["executionId"] == record["executionId"]


def test_release_returns_a_claimed_ticket_to_the_queue(service, authority):  # noqa: F811
    office, other, tid = worker(service), worker(service, "office-2"), issued(service)
    record = claim_execution(authority)
    send(service, office, "ticket.claim", {"ticketId": tid, "executionId": record["executionId"]})
    assert refused(service, other, "ticket.release", {"ticketId": tid}).code == "ticket_not_held"
    assert send(service, office, "ticket.release", {"ticketId": tid}) == {"ticket": {"ticketId": tid,
                                                                                    "status": "issued"}}
    full = ticket.get(service, "draft", tid)
    assert full["sessionId"] is None and full["machine"]["executionId"] is None
    assert send(service, other, "ticket.claim", {"ticketId": tid})["ticket"]["status"] == "claimed"
    send(service, other, "ticket.feedback", {"ticketId": tid, "kind": "idea", "text": "Později."})
    assert refused(service, other, "ticket.release", {"ticketId": tid}).code == "ticket_state"  # rozpracovaný ne
