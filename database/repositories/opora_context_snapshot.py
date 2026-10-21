"""Bounded private raw snapshot of enrolled SQL context sources."""
import json
import re

from database.repositories.opora_context_events import checkpoint
from database.repositories.opora_context_events_sources import MAX_HISTORY, SOURCES

VERSION = 1
MAX_ROWS = 8192
MAX_BYTES = 8 * 1024 * 1024
PRIMARY_KEYS = {
    "desktop_v3_state": ("project_id", "workspace_id"),
    "node_spec_revisions": ("project_id", "workspace_id", "node_id", "revision"),
    "node_text_revisions": ("project_id", "workspace_id", "node_id", "revision"),
    "drawing_revisions": ("project_id", "workspace_id", "layer_id", "revision"),
    "project_settings": ("project_id",),
    "project_profile": ("project_id",),
    "project_architecture": ("project_id",),
    "workspace_graph_authority": ("project_id", "workspace_id"),
}


def _validate_rows(project, rows):
    if not isinstance(rows, dict) or set(rows) != set(SOURCES):
        raise ValueError("Malformed SQL context snapshot sources.")
    count = 0
    for table, columns in SOURCES.items():
        values = rows[table]
        if not isinstance(values, list):
            raise TypeError("Malformed SQL context snapshot rows.")
        seen = set()
        previous = None
        for row in values:
            if not isinstance(row, dict) or set(row) != set(columns):
                raise ValueError("Malformed SQL context snapshot row.")
            for name, value in row.items():
                expected = int if name == "revision" else str
                if value is not None and type(value) is not expected:
                    raise ValueError("Malformed SQL context snapshot value type.")
            if row["project_id"] != project:
                raise ValueError("Foreign SQL context snapshot row.")
            key = tuple(row[name] for name in PRIMARY_KEYS[table])
            if any(value is None for value in key) or key in seen:
                raise ValueError("Null or duplicate SQL context snapshot primary key.")
            if previous is not None and key <= previous:
                raise ValueError("Noncanonical SQL context snapshot row order.")
            seen.add(key)
            previous = key
            count += 1
            if count > MAX_ROWS:
                raise ValueError("SQL context snapshot row bound exceeded.")
    encoded = json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("SQL context snapshot byte bound exceeded.")


def validate_snapshot(snapshot):
    if (not isinstance(snapshot, dict) or set(snapshot) !=
            {"version", "schema", "project", "checkpoint", "rows"}):
        raise ValueError("Malformed SQL context snapshot.")
    if type(snapshot["version"]) is not int or snapshot["version"] != VERSION:
        raise ValueError("Unsupported SQL context snapshot version.")
    if snapshot["schema"] != {table: list(cols) for table, cols in SOURCES.items()}:
        raise ValueError("SQL context snapshot schema mismatch.")
    project = snapshot["project"]
    if not isinstance(project, str) or not project:
        raise ValueError("Malformed SQL context snapshot project.")
    point = snapshot["checkpoint"]
    if (not isinstance(point, dict) or set(point) != {"coverageId", "sequence"}
            or not isinstance(point["coverageId"], str)
            or re.fullmatch(r"[0-9a-f]{32}", point["coverageId"]) is None
            or type(point["sequence"]) is not int
            or not 0 <= point["sequence"] <= MAX_HISTORY):
        raise ValueError("Malformed SQL context snapshot checkpoint.")
    _validate_rows(project, snapshot["rows"])
    if len(json.dumps(snapshot, ensure_ascii=True, separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
        raise ValueError("SQL context snapshot byte bound exceeded.")
    return project, point


def _validate_state(project, rows):
    _validate_rows(project, rows)
    envelope = {"version": VERSION, "schema": {table: list(cols) for table, cols in SOURCES.items()},
                "project": project, "checkpoint": {"coverageId": "0" * 32, "sequence": 0},
                "rows": rows}
    if len(json.dumps(envelope, ensure_ascii=True, separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
        raise ValueError("SQL context snapshot byte bound exceeded.")


def capture(db, project):
    """Capture enrolled raw rows in the caller's transaction; never commits."""
    if not db.in_transaction:
        raise RuntimeError("SQL context snapshot requires caller transaction.")
    point = checkpoint(db, project)
    total_rows = total_bytes = 0
    for table, columns in SOURCES.items():
        lengths = "+".join(f"length(CAST(COALESCE(\"{column}\",'') AS BLOB))" for column in columns)
        count, size = db.execute(
            f'SELECT count(*),COALESCE(sum({lengths}),0) FROM "{table}" WHERE project_id=?',
            (project,),
        ).fetchone()
        total_rows += count
        # JSON escaping can expand every source byte; reserve sixfold plus row/field syntax.
        labels = sum(len(column.encode("utf-8")) * 6 + 8 for column in columns)
        total_bytes += size * 6 + count * (96 + labels)
    if total_rows > MAX_ROWS or total_bytes > MAX_BYTES:
        raise ValueError("SQL context snapshot bounds exceeded.")
    rows = {}
    for table, columns in SOURCES.items():
        projection = ",".join(f'"{column}"' for column in columns)
        ordered = ",".join(f'"{column}"' for column in PRIMARY_KEYS[table])
        values = db.execute(
            f'SELECT {projection} FROM "{table}" WHERE project_id=? ORDER BY {ordered} LIMIT ?',
            (project, MAX_ROWS + 1),
        ).fetchall()
        if len(values) > MAX_ROWS:
            raise ValueError("SQL context snapshot row bound exceeded.")
        rows[table] = [dict(zip(columns, tuple(row))) for row in values]
    result = {"version": VERSION, "schema": {table: list(cols) for table, cols in SOURCES.items()},
              "project": project, "checkpoint": {"coverageId": point["coverageId"],
                                                     "sequence": point["sequence"]},
              "rows": rows}
    _validate_state(project, rows)
    if len(json.dumps(result, ensure_ascii=True, separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
        raise ValueError("SQL context snapshot byte bound exceeded.")
    return result
