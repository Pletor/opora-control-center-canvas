"""Expand-only milestone replacement provenance; legacy history remains explicitly unknown.

Rollback keeps this nullable column. Older readers and writers name their original
columns and safely ignore it; old activations simply cannot assert new provenance.
"""
import sqlite3


def ensure_milestone_lifecycle(db):
    columns = {row[1] for row in db.execute("PRAGMA table_info(intake_milestones)")}
    if not columns or "replaced_by" in columns:
        return
    try:
        db.execute("ALTER TABLE intake_milestones ADD COLUMN replaced_by TEXT")
    except sqlite3.OperationalError:
        if "replaced_by" not in {row[1] for row in db.execute("PRAGMA table_info(intake_milestones)")}:
            raise  # A concurrent successful expansion is safe; every other partial failure remains visible.
