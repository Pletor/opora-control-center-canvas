"""Starší databáze projektu dostane sloupce oddělení a profilu ticketu; opakované otevření nic nemění."""
import sqlite3

from database.schema.project_initialization import initialize_project_schema


def test_old_tickets_table_gets_department_and_profile():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE tickets(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, project_id TEXT"
               " NOT NULL, workspace_id TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL, card_id TEXT,"
               " execution_id TEXT, card_version INTEGER, session_id TEXT, delivery TEXT, created_at TEXT NOT NULL,"
               " updated_at TEXT NOT NULL)")
    initialize_project_schema(db)
    initialize_project_schema(db)
    columns = [row[1] for row in db.execute("PRAGMA table_info(tickets)")]
    assert columns[-2:] == ["department", "profile"]
