"""The same additive schema initialization for first open and historical backup restore."""
import sqlite3

from database.schema.project_schema import (
    PROJECT_SCHEMA,
    ensure_brief_fragment_columns,
    ensure_canvas_version_columns,
    ensure_milestone_proposed,
    ensure_ticket_columns,
    ensure_ticket_feedback_heart,
)


def initialize_project_schema(db):
    """Each additive step is witnessed on its own, so a generation row names the exact step."""
    from database.repositories.opora_context_events import install
    from database.repositories.schema_generations import witness
    from database.schema.dead_tables import drop_dead_tables, drop_retired_tables
    from database.schema.milestone_lifecycle import ensure_milestone_lifecycle
    from database.schema.opora_event_schema import ensure_process_columns
    from database.schema.opora_review_gate_schema import ensure_review_job_kind
    steps = [("PROJECT_SCHEMA (nové tabulky, indexy a triggery projektu)", lambda: db.executescript(PROJECT_SCHEMA))]
    steps += [(step.__name__, lambda step=step: step(db)) for step in (
        ensure_canvas_version_columns, ensure_brief_fragment_columns, ensure_ticket_columns,
        ensure_milestone_proposed, ensure_ticket_feedback_heart, ensure_milestone_lifecycle,
        ensure_review_job_kind, ensure_process_columns)]
    steps += [("opora_context_events.install (triggery SQL kontextu)", lambda: install(db)),
              ("drop_dead_tables", lambda: drop_dead_tables(db)),
              ("drop_retired_tables", lambda: drop_retired_tables(db))]
    for name, step in steps:
        witness(db, "initialize_project_schema: " + name, step)


def restore_project_backup(db, path):
    """Restore into the existing connection, then upgrade historical additive schema."""
    source = sqlite3.connect(path)
    try:
        source.backup(db)
        initialize_project_schema(db)
        db.commit()
    finally:
        source.close()
