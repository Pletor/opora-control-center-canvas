"""Migrace ticketu je aditivní a idempotentní: staré lístky otázek v `gate_tickets` zůstanou beze změny."""
import sqlite3

from database.repositories.tickets import TicketStore
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_SCHEMA, PROJECT_TABLES

OLD_TICKET = ("INSERT INTO gate_tickets(id,project_id,workspace_id,session_id,kind,body,status,created_at)"
              " VALUES('gt_old','draft','draft','gs_1','ask','{\"question\":\"?\"}','queued','2026-11-01T00:00:00Z')")


def test_old_project_gains_ticket_tables_and_keeps_question_tickets(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    old = PROJECT_SCHEMA.split("CREATE TABLE IF NOT EXISTS tickets(")[0]  # databáze z doby před ticketem
    db.executescript(old + "\n" + OLD_TICKET + ";")
    db.commit()
    assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='tickets'").fetchone()
    initialize_project_schema(db)
    db.commit()
    version = db.execute("PRAGMA schema_version").fetchone()[0]
    initialize_project_schema(db)  # druhé otevření: žádné DDL
    db.commit()
    assert db.execute("PRAGMA schema_version").fetchone()[0] == version
    assert db.execute("SELECT id, kind, status FROM gate_tickets").fetchall() == [("gt_old", "ask", "queued")]
    store = TicketStore(db, "draft")
    store.insert("tk_1", "draft", "issued", {"essence": "x"}, {"cardId": "hero"}, "2026-11-03T00:00:00Z")
    assert store.move("tk_1", "issued", "claimed", "2026-11-03T00:00:01Z", session_id="gs_1")
    assert not store.move("tk_1", "issued", "claimed", "2026-11-03T00:00:02Z")  # compare-and-set
    store.add_feedback("tf_1", "tk_1", "question", "?", "gs_1", "2026-11-03T00:00:03Z")
    assert store.open_questions("tk_1") == 1 and store.answer_feedback("tf_1", {"text": "!"}, "t")
    assert not store.answer_feedback("tf_1", {"text": "!"}, "t") and store.open_questions("tk_1") == 0
    ticket = store.get("tk_1")
    assert ticket["status"] == "claimed" and ticket["machine"]["cardId"] == "hero" and ticket["feedback"][0]["answer"]
    assert store.held_by("gs_1")["ticketId"] == "tk_1" and store.oldest_issued("draft") is None
    assert PROJECT_TABLES["tickets"] == PROJECT_TABLES["ticket_feedback"] == "project_id"
    db.close()
