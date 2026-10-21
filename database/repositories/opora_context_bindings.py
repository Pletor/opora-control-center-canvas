"""Opt-in registry source fence. Caller holds registry_lock; no cross-DB atomicity."""
import hashlib
import json
import sqlite3
import uuid

from database.repositories.opora_context_binding_triggers import SOURCES, TABLE, statements, verify
from database.schema.opora_context_binding_schema import SCHEMA


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _schema(db):
    result = {}
    for table, columns in SOURCES.items():
        rows = [tuple(row) for row in db.execute(f'PRAGMA table_info("{table}")')]
        if [(row[1], row[2]) for row in rows] != [(name, "TEXT") for name in columns.split()]:
            raise ValueError("Registry binding source schema unavailable.")
        result[table] = rows
    result[TABLE] = [tuple(row) for row in db.execute(f"PRAGMA table_info({TABLE})")]
    return _digest(result)


def install(db):
    """Add guards only before first enrollment; never repair a missing enrolled guard."""
    db.execute(SCHEMA)
    db.execute("PRAGMA recursive_triggers=ON")
    if db.execute(f"SELECT 1 FROM {TABLE} LIMIT 1").fetchone():
        return
    existing = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
    for name, sql in statements().items():
        if name not in existing:
            db.execute(sql)
    verify(db)


def _sources(db, project, workspace):
    if not all(isinstance(value, str) and 0 < len(value) <= 128 for value in (project, workspace)):
        raise ValueError("Registry binding requires project and workspace IDs.")
    values = {}
    for table in SOURCES:
        key = "id" if table == "projects" else "project_id"
        query, args = f"SELECT * FROM {table} WHERE {key}=?", (project,)
        if table in ("workspaces", "archived_workspaces"):
            query += " AND id=?"
            args += (workspace,)
        # Reject oversized or non-text fields in SQL before materializing them.
        invalid = " OR ".join(
            f"(typeof({column}) NOT IN ('text','null') OR length(CAST({column} AS BLOB))>8192)"
            for column in SOURCES[table].split()
        )
        bounded = query.replace("SELECT *", "SELECT 1") + f" AND ({invalid}) LIMIT 1"
        if db.execute(bounded, args).fetchone():
            raise ValueError("Registry source binding metadata exceeds bounds.")
        values[table] = [list(row) for row in db.execute(query, args)]
    if values["archived_projects"] or values["archived_workspaces"]:
        raise ValueError("Archived registry binding is unavailable.")
    if project == "draft":
        valid = workspace == "draft" and bool(values["builtin_project_metadata"])
    else:
        source = values["project_sources"]
        kind = source[0][1] if source else "git"
        valid = bool(values["projects"]) and (
            workspace == "draft" if kind in ("local", "empty") else
            kind == "git" and (workspace == "main" or bool(values["workspaces"]))
        )
    if not valid:
        raise ValueError("Missing or mismatched registry source binding.")
    if any(field is not None and (not isinstance(field, str) or len(field.encode()) > 8192)
           for rows in values.values() for row in rows for field in row):
        raise ValueError("Registry source binding metadata exceeds bounds.")
    if len(json.dumps(values).encode()) > 65536:
        raise ValueError("Registry source binding exceeds bounds.")
    return values


def enroll(db, project, workspace):
    if not db.in_transaction:
        raise RuntimeError("Registry binding enrollment requires caller transaction.")
    if not db.execute(f"SELECT 1 FROM {TABLE} WHERE project_id=? AND workspace_id=?", (project, workspace)).fetchone():
        _sources(db, project, workspace)
        schema, triggers = _schema(db), _digest(verify(db))
        if not db.execute("PRAGMA recursive_triggers").fetchone()[0]:
            raise ValueError("Registry binding requires recursive triggers.")
        db.execute(f"INSERT INTO {TABLE}(project_id,workspace_id,identity,schema_digest,trigger_digest,schema_version) VALUES(?,?,?,?,?,?)",
                   (project, workspace, uuid.uuid4().hex, schema, triggers, db.execute("PRAGMA schema_version").fetchone()[0]))
    return checkpoint(db, project, workspace)


def _checkpoint(db, project, workspace):
    try:
        row = db.execute(f"SELECT identity,generation,schema_digest,trigger_digest,schema_version,frozen FROM {TABLE} WHERE project_id=? AND workspace_id=?", (project, workspace)).fetchone()
        if row is None:
            raise ValueError("Registry source binding is not enrolled.")
        identity, generation, schema, triggers, version, frozen = row
        if (frozen is not None or not db.execute("PRAGMA recursive_triggers").fetchone()[0]
                or version != db.execute("PRAGMA schema_version").fetchone()[0]
                or schema != _schema(db) or triggers != _digest(verify(db))
                or not isinstance(identity, str) or len(identity) != 32
                or type(generation) is not int or not 0 <= generation <= 2147483647):
            raise ValueError("Registry source binding coverage unavailable.")
        return {"identity": identity, "generation": generation, "schemaDigest": schema,
                "triggerDigest": triggers, "schemaVersion": version,
                "sources": _sources(db, project, workspace)}
    except sqlite3.Error as exc:
        raise ValueError("Registry source binding storage unavailable.") from exc


def checkpoint(db, project, workspace):
    """One registry read snapshot, retaining a caller's enrollment transaction."""
    owns = not db.in_transaction
    if owns:
        db.execute("BEGIN")
    try:
        return _checkpoint(db, project, workspace)
    finally:
        if owns:
            db.rollback()
