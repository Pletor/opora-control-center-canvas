"""The same additive schema initialization for first open and historical backup restore."""
import sqlite3

from database.schema.project_schema import (
    PROJECT_SCHEMA,
    ensure_brief_fragment_columns,
    ensure_canvas_version_columns,
)


def initialize_project_schema(db):
    db.executescript(PROJECT_SCHEMA)
    ensure_canvas_version_columns(db)
    ensure_brief_fragment_columns(db)
    from database.schema.opora_review_gate_schema import ensure_review_job_kind
    ensure_review_job_kind(db)
    from database.schema.opora_event_schema import ensure_process_columns
    ensure_process_columns(db)
    from database.repositories.opora_context_events import install
    install(db)


def restore_project_backup(db, path):
    """Restore into the existing connection, then upgrade historical additive schema."""
    source = sqlite3.connect(path)
    try:
        source.backup(db)
        initialize_project_schema(db)
        db.commit()
    finally:
        source.close()
