"""Additive execution schema is restart-safe and preserves existing ownership records."""
import sqlite3

from database.schema.opora_execution_schema import SCHEMA


def test_schema_reopen_preserves_legacy_leases_enrollment_and_receipts(tmp_path):
    path = tmp_path / "project.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE card_leases(project_id,workspace_id,node_id,owner,token,expires_at)")
        db.execute("INSERT INTO card_leases VALUES('p','w','n','legacy','secret',10)")
        db.executescript(SCHEMA)
        db.execute("INSERT INTO opora_execution_epochs VALUES('p','w','n',5)")
        db.execute("INSERT INTO opora_execution_results VALUES('p','w','run','request','digest','{}')")
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        assert db.execute("SELECT owner FROM card_leases").fetchone()[0] == "legacy"
        assert db.execute("SELECT epoch FROM opora_execution_epochs").fetchone()[0] == 5
        assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 1
