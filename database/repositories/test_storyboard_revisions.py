import json
import sqlite3

import pytest

from database.repositories.storyboard_revisions import StoryboardRevisions
from database.schema.storyboard_schema import SCHEMA


@pytest.fixture
def store():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    yield StoryboardRevisions(db, "p", "w", "n")
    db.close()


@pytest.mark.parametrize("record", [
    {"revision": 7, "schema": "opora.storyboard/1", "moments": [{"id": "m-12345678", "t": 0}]},
    {"revision": 8, "deleted": True, "updatedAt": "2026-11-09T00:00:00Z"},
])
def test_exact_import_idempotence_sql_authority_and_export(store, tmp_path, record):
    path = tmp_path / "legacy.json"
    raw = json.dumps(record, indent=4)
    path.write_text(raw, encoding="utf-8")
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        assert store.import_legacy(path)["record"] == record
    path.write_text('{"revision":999,"deleted":true}', encoding="utf-8")
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        assert store.import_legacy(path)["record"] == record
        replacement = {"revision": record["revision"] + 1, "deleted": True}
        store.append(record["revision"], replacement)
    assert store.read(record["revision"])["record"] == record
    exported = tmp_path / "rollback" / "n.json"
    assert store.export_legacy(exported)["revision"] == replacement["revision"]
    assert json.loads(exported.read_text(encoding="utf-8")) == replacement
    with pytest.raises(ValueError, match="overwrite"):
        store.export_legacy(exported)
    for sql in ("DELETE FROM storyboard_revisions", "UPDATE storyboard_revisions SET record='{}'",
                "INSERT OR REPLACE INTO storyboard_revisions SELECT * FROM storyboard_revisions"):
        with pytest.raises(sqlite3.IntegrityError):
            store.db.execute(sql)
        store.db.rollback()


def test_rollback_and_empty_reads_do_not_create_sources(store, tmp_path):
    assert store.read()["revision"] == 0
    assert store.latest() is None and not store.db.in_transaction
    with pytest.raises(RuntimeError, match="transaction"):
        store.insert(1, {"revision": 1})
    with pytest.raises(ValueError):
        with store.db:
            store.db.execute("BEGIN IMMEDIATE")
            store.append(0, {"revision": 1, "deleted": True})
            raise ValueError("forced rollback")
    assert store.latest() is None
    assert store.export_legacy(tmp_path / "absent.json")["filePresent"] is False
    assert not (tmp_path / "absent.json").exists()
