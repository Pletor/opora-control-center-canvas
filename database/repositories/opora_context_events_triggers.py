"""Static trigger generation shared by installation and exact integrity checks."""
from database.repositories.opora_context_events_sources import (
    EVENT_LIMIT,
    MAX_HISTORY,
    PROJECT_LIMIT,
    SOURCES,
    raw,
)


def statements():
    result = {}
    guards = {
        "events_update": "BEFORE UPDATE ON opora_context_events BEGIN SELECT RAISE(ABORT,'Immutable context event'); END",
        "events_delete": "BEFORE DELETE ON opora_context_events BEGIN SELECT RAISE(ABORT,'Immutable context event'); END",
        "events_replace": "BEFORE INSERT ON opora_context_events WHEN EXISTS(SELECT 1 FROM opora_context_events WHERE project_id=NEW.project_id AND sequence=NEW.sequence) BEGIN SELECT RAISE(ABORT,'Immutable context event'); END",
        "coverage_delete": "BEFORE DELETE ON opora_context_coverage BEGIN SELECT RAISE(ABORT,'Permanent context coverage'); END",
        "coverage_replace": "BEFORE INSERT ON opora_context_coverage WHEN EXISTS(SELECT 1 FROM opora_context_coverage WHERE project_id=NEW.project_id) BEGIN SELECT RAISE(ABORT,'Permanent context coverage'); END",
        "coverage_identity": "BEFORE UPDATE ON opora_context_coverage WHEN NEW.project_id IS NOT OLD.project_id OR NEW.coverage_id IS NOT OLD.coverage_id OR NEW.schema_digest IS NOT OLD.schema_digest OR NEW.trigger_digest IS NOT OLD.trigger_digest OR NEW.schema_version IS NOT OLD.schema_version OR (OLD.frozen IS NOT NULL AND NEW.frozen IS NOT OLD.frozen) BEGIN SELECT RAISE(ABORT,'Permanent context coverage'); END",
        "event_counter": "AFTER INSERT ON opora_context_events BEGIN UPDATE opora_context_coverage SET sequence=NEW.sequence,bytes=bytes+NEW.bytes WHERE project_id=NEW.project_id; END",
    }
    for name, body in guards.items():
        key = "opora_context_" + name
        result[key] = f"CREATE TRIGGER {key} {body}"
    for table, columns in SOURCES.items():
        for operation in ("INSERT", "UPDATE", "DELETE"):
            before = "NULL" if operation == "INSERT" else raw("OLD", columns)
            after = "NULL" if operation == "DELETE" else raw("NEW", columns)
            size = f"(COALESCE(length(CAST({before} AS BLOB)),0)+COALESCE(length(CAST({after} AS BLOB)),0))"
            aliases = ("NEW",) if operation == "INSERT" else (("OLD",) if operation == "DELETE" else ("OLD", "NEW"))
            body = []
            bad = " OR ".join(f"typeof({alias}.\"{column}\") NOT IN ('null','integer','text')" for alias in aliases for column in columns)
            for alias in aliases:
                scope = f"project_id={alias}.project_id"
                if operation == "UPDATE" and alias == "NEW":
                    scope += " AND NEW.project_id IS NOT OLD.project_id"
                body.append(f"UPDATE opora_context_coverage SET frozen='writer configuration or value unavailable' WHERE {scope} AND frozen IS NULL AND ((SELECT recursive_triggers FROM pragma_recursive_triggers)=0 OR {bad});")
                body.append(f"UPDATE opora_context_coverage SET frozen='context history or byte limit exceeded' WHERE {scope} AND frozen IS NULL AND ({size}>{EVENT_LIMIT} OR bytes+{size}>{PROJECT_LIMIT} OR sequence>={MAX_HISTORY});")
                body.append(f"INSERT INTO opora_context_events(project_id,sequence,coverage_id,source_table,operation,before_json,after_json,bytes) SELECT project_id,sequence+1,coverage_id,'{table}','{operation}',{before},{after},{size} FROM opora_context_coverage WHERE {scope} AND frozen IS NULL;")
            name = f"opora_context_{table}_{operation.lower()}"
            result[name] = f'CREATE TRIGGER {name} AFTER {operation} ON "{table}" BEGIN ' + " ".join(body) + " END"
    return result


def verify_triggers(db):
    expected = statements()
    actual = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'opora_context_%'"))
    if expected != actual:
        raise ValueError("SQL context trigger coverage is unavailable.")
    return expected


def install(db):
    db.execute("PRAGMA recursive_triggers=ON")
    existing = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
    enrolled = db.execute("SELECT 1 FROM opora_context_coverage LIMIT 1").fetchone()
    for name, sql in statements().items():
        if name not in existing and not enrolled:
            db.execute(sql)
    if not enrolled:
        verify_triggers(db)
