"""Replay bounded journal evidence against a private raw SQL snapshot."""
import copy
import hashlib
import json

from database.repositories.opora_context_events import checkpoint
from database.repositories.opora_context_events import transitions as load_transitions
from database.repositories.opora_context_events_sources import SOURCES
from database.repositories.opora_context_snapshot import (
    MAX_ROWS,
    PRIMARY_KEYS,
    _validate_state,
    capture,
    validate_snapshot,
)

MAX_TRANSITIONS = 256


def _semantic_digest(projector, rows):
    value = projector(copy.deepcopy(rows))
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _apply(project, rows, event):
    table = event["sourceTable"]
    columns = SOURCES[table]
    old, new = event["before"], event["after"]
    if old is not None and old["project_id"] == project:
        key = tuple(old[name] for name in PRIMARY_KEYS[table])
        matches = [i for i, row in enumerate(rows[table])
                   if tuple(row[name] for name in PRIMARY_KEYS[table]) == key]
        if len(matches) != 1 or rows[table][matches[0]] != old:
            raise ValueError("SQL context replay before-row mismatch.")
        rows[table].pop(matches[0])
    if new is not None and new["project_id"] == project:
        key = tuple(new[name] for name in PRIMARY_KEYS[table])
        if any(tuple(row[name] for name in PRIMARY_KEYS[table]) == key for row in rows[table]):
            raise ValueError("SQL context replay duplicate after-row.")
        rows[table].append({name: new[name] for name in columns})
        rows[table].sort(key=lambda row: tuple(row[name] for name in PRIMARY_KEYS[table]))
    if sum(len(value) for value in rows.values()) > MAX_ROWS:
        raise ValueError("SQL context replay row bound exceeded.")


def replay(db, origin, projector, limit=MAX_TRANSITIONS):
    """Validate raw transitions and return narrow live-scope continuity evidence.

    Projector signature: ``projector(raw_rows) -> JSON value``.
    The callback is server-owned and receives a deep copy for each evaluation.
    """
    project, start = validate_snapshot(origin)
    if not db.in_transaction:
        raise RuntimeError("SQL context replay requires caller transaction.")
    if not callable(projector) or type(limit) is not int or not 1 <= limit <= MAX_TRANSITIONS:
        raise ValueError("Invalid SQL context replay bounds or projector.")
    rows = copy.deepcopy(origin["rows"])
    baseline = _semantic_digest(projector, rows)
    sequence = start["sequence"]
    events = load_transitions(db, project, sequence, limit)
    for offset, event in enumerate(events, 1):
        if (event["sequence"] != sequence + offset
                or event["coverageId"] != start["coverageId"]):
            raise ValueError("SQL context replay sequence is discontinuous.")
        _apply(project, rows, event)
        _validate_state(project, rows)
        if _semantic_digest(projector, rows) != baseline:
            raise ValueError("SQL context live scope changed during replay.")
    head = checkpoint(db, project)
    expected_sequence = sequence + len(events)
    if head["coverageId"] != start["coverageId"] or head["sequence"] != expected_sequence:
        raise ValueError("SQL context replay does not reach current checkpoint.")
    current = capture(db, project)
    if current["rows"] != rows:
        raise ValueError("SQL context replay raw state differs from current snapshot.")
    return {"liveScopeUnchanged": True, "transitionCount": len(events),
            "sourceRowCount": sum(len(value) for value in rows.values()),
            "checkpoint": {"coverageId": head["coverageId"], "sequence": head["sequence"]}}
