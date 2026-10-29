"""Lístky brány: pořadí `seq`, jediná odpověď a schránka jen se zodpovězenými lístky jedné relace."""
import sqlite3

import pytest

from database.repositories.gate_tickets import GateTicketStore
from database.schema.project_initialization import initialize_project_schema

AT = "2026-10-28T10:00:00Z"


@pytest.fixture
def store():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    yield GateTicketStore(connection, "p1")
    connection.close()


def test_ticket_starts_queued_and_is_answered_once(store):
    seq = store.insert("gt_1", "main", "gs_1", "ask", {"question": "Smím?"}, AT)
    ticket = store.get("gt_1")
    assert ticket["seq"] == seq and ticket["status"] == "queued" and ticket["answer"] is None
    assert ticket["body"] == {"question": "Smím?"}
    assert store.answer("gt_1", {"text": "Ano"}, "human", AT) is True
    assert store.answer("gt_1", {"text": "Ne"}, "human", AT) is False
    answered = store.get("gt_1")
    assert answered["status"] == "answered" and answered["answer"] == {"text": "Ano"}
    assert answered["answeredBy"] == "human" and answered["answeredAt"] == AT


def test_answered_after_is_per_session_and_cursor(store):
    store.insert("gt_1", "main", "gs_1", "ask", {}, AT)
    store.insert("gt_2", "main", "gs_2", "ask", {}, AT)
    store.insert("gt_3", "main", "gs_1", "ask", {}, AT)
    for ticket in ("gt_1", "gt_2", "gt_3"):
        store.answer(ticket, "ok", "human", AT)
    box = store.answered_after("gs_1", 0, 10)
    assert [t["ticketId"] for t in box] == ["gt_1", "gt_3"]
    assert [t["ticketId"] for t in store.answered_after("gs_1", box[0]["answeredSeq"], 10)] == ["gt_3"]
    assert GateTicketStore(store.db, "p2").answered_after("gs_1", 0, 10) == []
    # Lístek zodpovězený branou hned v požadavku (audit synchronního druhu) do schránky nejde.
    store.insert("gt_4", "main", "gs_1", "state", {}, AT)
    store.answer("gt_4", {"queue": {}}, "gate", AT)
    assert [t["ticketId"] for t in store.answered_after("gs_1", 0, 10)] == ["gt_1", "gt_3"]


def test_ticket_answered_later_is_not_lost_behind_the_cursor(store):
    # Mladší lístek zodpovězený dřív posune kurzor; starší zodpovězený potom se musí ve schránce objevit.
    store.insert("gt_old", "main", "gs_1", "ask", {}, AT)
    store.insert("gt_new", "main", "gs_1", "ask", {}, AT)
    store.answer("gt_new", "ok", "human", AT)
    cursor = store.answered_after("gs_1", 0, 10)[-1]["answeredSeq"]
    store.answer("gt_old", "ok", "human", AT)
    assert [t["ticketId"] for t in store.answered_after("gs_1", cursor, 10)] == ["gt_old"]


def test_queued_lists_what_still_waits(store):
    store.insert("gt_1", "main", "gs_1", "ask", {}, AT)
    store.insert("gt_2", "main", "gs_1", "change", {}, AT)
    store.answer("gt_1", "ok", "human", AT)
    assert [t["ticketId"] for t in store.queued("main", 10)] == ["gt_2"]
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE gate_tickets SET status='done'")


def _session(store, session_id, role):
    store.db.execute("INSERT INTO gate_sessions(id,project_id,workspace_id,role,worker_name,worker_meta,token_hash,"
                     "created_at) VALUES(?,?,?,?,?,?,?,?)", (session_id, "p1", "main", role, role, "{}",
                                                             "h_" + session_id, AT))


def test_escalations_are_heart_questions_for_the_human_newest_first(store):
    _session(store, "gs_heart", "heart")
    _session(store, "gs_dev", "worker")
    store.insert("gt_1", "main", "gs_heart", "ask", {"text": "Barva?", "for": "human"}, AT)
    store.insert("gt_2", "main", "gs_heart", "ask", {"text": "Font?", "for": "human"}, AT)
    store.insert("gt_3", "main", "gs_dev", "ask", {"text": "Smím?", "for": "human"}, AT)  # pracovník, ne srdce
    store.insert("gt_4", "main", "gs_heart", "ask", {"question": "?"}, AT)  # ne pro člověka
    store.insert("gt_5", "draft", "gs_heart", "ask", {"text": "Jinde", "for": "human"}, AT)
    store.answer("gt_1", {"text": "Modrá"}, "human", AT)
    assert [t["ticketId"] for t in store.escalations("main", 10)] == ["gt_2"]
    store.insert("gt_6", "main", "gs_heart", "ask", {"text": "Logo?", "for": "human"}, AT)
    assert [t["ticketId"] for t in store.escalations("main", 10)] == ["gt_6", "gt_2"]
    assert store.heart_escalation_workspace("gt_1") == "main"
    assert store.heart_escalation_workspace("gt_5") == "draft"
    assert store.heart_escalation_workspace("gt_3") is None
    assert store.heart_escalation_workspace("gt_4") is None
    assert store.heart_escalation_workspace("gt_none") is None
