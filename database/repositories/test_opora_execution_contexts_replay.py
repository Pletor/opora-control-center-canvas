"""Canonical private storage must preserve semantic snapshot replay compatibility."""
import copy
import sqlite3

import pytest

from database.repositories import opora_execution_contexts as contexts
from database.repositories.opora_context_events import enroll
from database.repositories.opora_context_replay import replay
from database.repositories.opora_context_snapshot import capture, validate_snapshot
from database.schema.project_initialization import initialize_project_schema


def test_captured_snapshot_replays_after_private_canonical_storage():
    db = sqlite3.connect(":memory:")
    try:
        initialize_project_schema(db)
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        contexts.key(db, "p", create=True)
        enroll(db, "p")
        db.execute("INSERT INTO project_profile VALUES('p','layered','single')")
        db.execute("INSERT INTO node_text_revisions VALUES('p','w','a',1,'first','now')")
        db.execute("INSERT INTO node_text_revisions VALUES('p','w','z',1,'last','now')")
        origin = capture(db, "p")
        contexts.insert(db, "p", "w", "e", {"snapshot": origin})
        restored = contexts.read(db, "p", "w", "e")["snapshot"]
        assert restored == origin
        assert tuple(restored) != tuple(origin)
        evidence = replay(db, restored, lambda rows: rows)
        assert evidence["liveScopeUnchanged"] is True
        assert evidence["transitionCount"] == 0
        assert evidence["sourceRowCount"] == 3
        for mutation in ("envelope", "sources", "row", "checkpoint", "pk-order"):
            malformed = copy.deepcopy(restored)
            if mutation == "envelope":
                malformed["extra"] = True
            elif mutation == "sources":
                malformed["rows"]["extra"] = []
            elif mutation == "row":
                malformed["rows"]["project_profile"][0]["extra"] = True
            elif mutation == "checkpoint":
                malformed["checkpoint"]["extra"] = True
            else:
                malformed["rows"]["node_text_revisions"].reverse()
            with pytest.raises(ValueError):
                validate_snapshot(malformed)
    finally:
        db.close()
