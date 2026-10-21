"""Every policy authority table independently protects historical evidence from restore."""
import sqlite3

import pytest

from backend.canvas.opora_review_policy_restore import refuse_policy_restore
from database.repositories.opora_review_attempts import Attempts
from database.repositories.opora_review_policy import Policies
from database.repositories.test_opora_review_policy import content
from database.schema.opora_review_policy_schema import SCHEMA


@pytest.mark.parametrize("kind", ["policy", "ref", "attempt"])
def test_each_policy_table_prevents_restore_without_changes(kind):
    with sqlite3.connect(":memory:") as db:
        db.executescript(SCHEMA)
        refuse_policy_restore(db)
        db.execute("BEGIN IMMEDIATE")
        if kind == "attempt":
            Attempts(db, "project", "workspace").begin(1, {"repository": "owner/repo", "branch": "main"},
                                                       "a" * 40, None, "2026-10-21T00:00:00Z")
        elif kind == "ref":
            db.execute("INSERT INTO opora_review_policy_refs VALUES('project','workspace',?)", ("f" * 40,))
        else:
            Policies(db, "project", "workspace").activate(content(), None)
            db.execute("DELETE FROM opora_review_policy_refs")
        db.commit()
        before = list(db.iterdump())
        with pytest.raises(ValueError, match="review policy"):
            refuse_policy_restore(db)
        assert list(db.iterdump()) == before
