"""Caller-owned, opt-in SQL history; files and resolver registries are not covered.

4096 transitions, 8 MiB per raw payload and 128 MiB per project are hard bounds.
Source writers freeze at these bounds and continue legacy writes. DDL generation
is pinned: even restoring a dropped guard cannot silently repair lost coverage.
SQLite database owners can forge all evidence; this is not a security boundary.
"""
import json
import sqlite3
import uuid

from database.repositories.opora_context_events_sources import (
    EVENT_LIMIT,
    MAX_HISTORY,
    PROJECT_LIMIT,
    SOURCES,
    digest,
    schema_digest,
)
from database.repositories.opora_context_events_triggers import install as install_triggers
from database.repositories.opora_context_events_triggers import verify_triggers


def install(db):
    """Install static triggers without committing the caller transaction."""
    install_triggers(db)


def enroll(db, project):
    if not db.in_transaction:
        raise RuntimeError("SQL context enrollment requires caller transaction.")
    if not isinstance(project, str) or not project:
        raise ValueError("A project ID is required.")
    existing = db.execute("SELECT 1 FROM opora_context_coverage WHERE project_id=?", (project,)).fetchone()
    if existing:
        return checkpoint(db, project)
    schema = schema_digest(db)
    triggers = digest(verify_triggers(db))
    if not db.execute("PRAGMA recursive_triggers").fetchone()[0]:
        raise ValueError("SQL context requires recursive triggers.")
    if db.execute("SELECT 1 FROM opora_context_events WHERE project_id=? LIMIT 1", (project,)).fetchone():
        raise ValueError("Orphaned SQL context history.")
    db.execute("INSERT INTO opora_context_coverage(project_id,coverage_id,schema_digest,trigger_digest,schema_version) VALUES(?,?,?,?,?)",
               (project, uuid.uuid4().hex, schema, triggers, db.execute("PRAGMA schema_version").fetchone()[0]))
    return checkpoint(db, project)


def _payload(value, table, project):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Malformed SQL context payload.")
    row = json.loads(value)
    if not isinstance(row, dict) or tuple(row) != SOURCES[table]:
        raise ValueError("Malformed SQL context row.")
    for name, field in row.items():
        if field is not None and type(field) is not (int if name == "revision" else str):
            raise ValueError("Malformed SQL context value type.")
    return row


def _verify_event(row, project, coverage, sequence):
    number, identity, table, operation, before, after, size = tuple(row)
    if number != sequence or identity != coverage or table not in SOURCES:
        raise ValueError("SQL context history is discontinuous.")
    if operation not in ("INSERT", "UPDATE", "DELETE"):
        raise ValueError("Malformed SQL context operation.")
    old, new = _payload(before, table, project), _payload(after, table, project)
    if ((operation == "INSERT" and (old is not None or new is None))
            or (operation == "DELETE" and (old is None or new is not None))
            or (operation == "UPDATE" and (old is None or new is None))):
        raise ValueError("Malformed SQL context transition.")
    if not any(value is not None and value["project_id"] == project for value in (old, new)):
        raise ValueError("Foreign SQL context history.")
    actual = sum(len(value.encode("utf-8")) for value in (before, after) if value is not None)
    if type(size) is not int or size != actual or not 0 < size <= EVENT_LIMIT:
        raise ValueError("Malformed SQL context payload bytes.")
    return {"sequence": number, "coverageId": identity, "sourceTable": table,
            "operation": operation, "before": old, "after": new, "bytes": size}


def _checkpoint(db, project):
    row = db.execute("SELECT coverage_id,schema_digest,trigger_digest,schema_version,sequence,bytes,frozen FROM opora_context_coverage WHERE project_id=?", (project,)).fetchone()
    if row is None:
        raise ValueError("SQL context project is not enrolled.")
    coverage, schema, triggers, version, sequence, size, frozen = tuple(row)
    if frozen is not None:
        raise ValueError("SQL context coverage is frozen: " + str(frozen))
    if not db.execute("PRAGMA recursive_triggers").fetchone()[0]:
        raise ValueError("SQL context recursive triggers are disabled.")
    if version != db.execute("PRAGMA schema_version").fetchone()[0]:
        raise ValueError("SQL context schema generation changed.")
    if schema != schema_digest(db) or triggers != digest(verify_triggers(db)):
        raise ValueError("SQL context schema or trigger fingerprint changed.")
    if (not isinstance(coverage, str) or len(coverage) != 32 or type(sequence) is not int
            or not 0 <= sequence <= MAX_HISTORY or type(size) is not int
            or not 0 <= size <= PROJECT_LIMIT):
        raise ValueError("SQL context history bounds unavailable.")
    counts = db.execute("SELECT count(*),COALESCE(sum(bytes),0),COALESCE(sum(length(CAST(COALESCE(before_json,'') AS BLOB))+length(CAST(COALESCE(after_json,'') AS BLOB))),0) FROM opora_context_events WHERE project_id=?", (project,)).fetchone()
    # Verify persisted and actual byte counts before bounded materialization.
    if tuple(counts) != (sequence, size, size):
        raise ValueError("SQL context event aggregate mismatch.")
    rows = db.execute("SELECT sequence,coverage_id,source_table,operation,before_json,after_json,bytes FROM opora_context_events WHERE project_id=? ORDER BY sequence LIMIT ?", (project, MAX_HISTORY + 1)).fetchall()
    if len(rows) != sequence:
        raise ValueError("SQL context event counter mismatch.")
    total = 0
    for number, event in enumerate(rows, 1):
        total += _verify_event(event, project, coverage, number)["bytes"]
    if total != size:
        raise ValueError("SQL context byte counter mismatch.")
    return {"coverageId": coverage, "sequence": sequence, "bytes": size,
            "sources": list(SOURCES), "fileSourcesCovered": False, "registriesCovered": False}


def checkpoint(db, project):
    # A read snapshot prevents mixing an old counter with newly committed events.
    owns = not db.in_transaction
    if owns:
        db.execute("BEGIN")
    try:
        return _checkpoint(db, project)
    except (sqlite3.DatabaseError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("SQL context evidence is unavailable.") from error
    finally:
        if owns:
            db.rollback()


def transitions(db, project, after, limit=256):
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= MAX_HISTORY:
        raise ValueError("Invalid SQL context history bounds.")
    owns = not db.in_transaction
    if owns:
        db.execute("BEGIN")
    try:
        head = checkpoint(db, project)
        if after > head["sequence"] or head["sequence"] - after > limit:
            raise ValueError("SQL context history exceeds requested bounds.")
        rows = db.execute("SELECT sequence,coverage_id,source_table,operation,before_json,after_json,bytes FROM opora_context_events WHERE project_id=? AND sequence>? ORDER BY sequence LIMIT ?", (project, after, limit + 1)).fetchall()
        return [_verify_event(row, project, head["coverageId"], after + index)
                for index, row in enumerate(rows, 1)]
    finally:
        if owns:
            db.rollback()
