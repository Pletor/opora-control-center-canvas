"""Private immutable origins with caller-owned transactions and bounded JSON storage."""
import hashlib
import json
import math
import re
import secrets

MAX_PIN = 9 * 1024 * 1024
MAX_PROOF = 64 * 1024
PROJECT_LIMIT = 64 * 1024 * 1024
_KEY = re.compile(r"[0-9a-f]{64}\Z")


def _identity(*values):
    if any(not isinstance(value, str) or not value or len(value) > 512
           or any(ord(char) < 32 for char in value) for value in values):
        raise ValueError("Invalid private context scope.")


def _tx(db):
    if not db.in_transaction:
        raise RuntimeError("Private context writes require caller transaction.")


def _encode(value, limit):
    if type(value) is not dict:
        raise ValueError("Private context JSON must be an object.")
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 64 or count > 200000:
            raise ValueError("Private context JSON complexity exceeds limit.")
        if type(item) is dict:
            if any(type(name) is not str for name in item):
                raise ValueError("Private context JSON keys must be strings.")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) not in (str, int, float, bool, type(None)):
            raise ValueError("Private context contains non-JSON values.")
        elif type(item) is float and not math.isfinite(item):
            raise ValueError("Private context contains non-finite numbers.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > limit:
            raise ValueError("Private context JSON exceeds size limit.")
        return encoded
    except (UnicodeError, OverflowError, RecursionError) as error:
        raise ValueError("Malformed private context JSON.") from error


def _decode(raw, limit):
    if not isinstance(raw, str) or len(raw) > limit:
        raise ValueError("Malformed stored private context JSON.")
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError as error:
        raise ValueError("Malformed stored private context JSON.") from error
    if size > limit:
        raise ValueError("Stored private context exceeds size limit.")

    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise ValueError("Duplicate private context JSON key.")
            result[name] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        if _encode(value, limit) != raw:
            raise ValueError("Stored private context JSON is not canonical.")
        return value
    except (TypeError, UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("Malformed stored private context JSON.") from error


def key(db, project, *, create=False):
    """Only explicit preparation may create a project secret, never repair a lost one."""
    _identity(project)
    row = db.execute("SELECT secret FROM opora_execution_context_keys WHERE project_id=?", (project,)).fetchone()
    if row:
        if not isinstance(row[0], str) or not _KEY.fullmatch(row[0]):
            raise ValueError("Malformed private context key.")
        return row[0]
    if not create or db.execute(
        "SELECT 1 FROM opora_execution_context_pins WHERE project_id=? LIMIT 1", (project,),
    ).fetchone():
        raise ValueError("Private context key is missing.")
    _tx(db)
    value = secrets.token_hex(32)
    db.execute("INSERT INTO opora_execution_context_keys VALUES(?,?)", (project, value))
    return value


def _quota(db, project, delta):
    used = db.execute(
        "SELECT COALESCE(SUM(length(CAST(pin_json AS BLOB))+COALESCE(length(CAST(proof_json AS BLOB)),0)),0)"
        " FROM opora_execution_context_pins WHERE project_id=?", (project,),
    ).fetchone()[0]
    if used + delta > PROJECT_LIMIT:
        raise ValueError("Private context project quota exceeded.")


def insert(db, project, workspace, execution_id, pin):
    """Persist exactly one private origin; caller must roll back on failure."""
    _tx(db)
    _identity(project, workspace, execution_id)
    key(db, project)
    raw = _encode(pin, MAX_PIN)
    _quota(db, project, len(raw.encode("utf-8")))
    db.execute("INSERT INTO opora_execution_context_pins VALUES(?,?,?,?,?,NULL)",
               (execution_id, project, workspace, raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()))


def _row(db, project, workspace, execution_id):
    _identity(project, workspace, execution_id)
    key(db, project)
    row = db.execute(
        "SELECT pin_json,pin_digest,proof_json FROM opora_execution_context_pins"
        " WHERE project_id=? AND workspace_id=? AND execution_id=?", (project, workspace, execution_id),
    ).fetchone()
    if not row:
        raise ValueError("Private context origin does not exist in this scope.")
    raw = row[0]
    pin = _decode(raw, MAX_PIN)
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != row[1]:
        raise ValueError("Private context origin integrity mismatch.")
    return pin, row[2]


def read(db, project, workspace, execution_id):
    return _row(db, project, workspace, execution_id)[0]


def proof(db, project, workspace, execution_id, value):
    """Replace only the latest public proof; never mutate the private origin."""
    _tx(db)
    _, old = _row(db, project, workspace, execution_id)
    raw = _encode(value, MAX_PROOF)
    _quota(db, project, len(raw.encode("utf-8")) - (len(old.encode("utf-8")) if old is not None else 0))
    db.execute("UPDATE opora_execution_context_pins SET proof_json=?"
               " WHERE project_id=? AND workspace_id=? AND execution_id=?", (raw, project, workspace, execution_id))


def read_proof(db, project, workspace, execution_id):
    _, raw = _row(db, project, workspace, execution_id)
    return _decode(raw, MAX_PROOF) if raw is not None else None
