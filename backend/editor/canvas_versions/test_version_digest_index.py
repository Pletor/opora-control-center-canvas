"""Dirty dotaz musí hledat v indexu, ne číst velké snapshoty pod zámkem."""
import sqlite3

import pytest

from database.schema.project_schema import PROJECT_SCHEMA, ensure_canvas_version_columns


@pytest.mark.parametrize("legacy", [False, True])
def test_version_digest_lookup_uses_covering_index_after_migration(legacy):
    with sqlite3.connect(":memory:") as db:
        if legacy:
            db.execute("CREATE TABLE canvas_versions(id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT)")
            db.execute("INSERT INTO canvas_versions VALUES('old','p','draft')")
        else:
            db.executescript(PROJECT_SCHEMA)
        ensure_canvas_version_columns(db)
        ensure_canvas_version_columns(db)
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT 1 FROM canvas_versions WHERE project_id=? AND workspace_id=? AND content_digest=? LIMIT 1",
            ("p", "draft", "digest"),
        ).fetchall()
        assert any("COVERING INDEX canvas_versions_content" in row[3] for row in plan), plan
        if legacy:
            assert db.execute("SELECT id,snapshot,content_digest FROM canvas_versions").fetchall() == [("old", None, None)]
