"""Fixed source allowlist; SQL identifiers never come from callers."""
import hashlib
import json

SOURCES = {
    "desktop_v3_state": ("project_id", "workspace_id", "revision", "state", "saved_at"),
    "node_spec_revisions": ("project_id", "workspace_id", "node_id", "revision", "fields", "saved_at"),
    "node_text_revisions": ("project_id", "workspace_id", "node_id", "revision", "text", "saved_at"),
    "drawing_revisions": ("project_id", "workspace_id", "layer_id", "revision", "scene", "saved_at"),
    "project_settings": ("project_id", "revision", "goal", "platform"),
    "project_profile": ("project_id", "architecture", "tenancy"),
    "project_architecture": ("project_id", "revision", "graph", "updated_at", "actor", "removed"),
    "workspace_graph_authority": ("project_id", "workspace_id", "revision", "graph", "digest"),
}
EVENT_LIMIT = 8 * 1024 * 1024
PROJECT_LIMIT = 128 * 1024 * 1024
MAX_HISTORY = 4096


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def schema_digest(db):
    result = []
    for table, columns in SOURCES.items():
        rows = [tuple(row) for row in db.execute(f'PRAGMA table_info("{table}")')]
        if tuple(row[1] for row in rows) != columns:
            raise ValueError("SQL context source schema is unavailable.")
        if any(row[2].upper() != ("INTEGER" if row[1] == "revision" else "TEXT") for row in rows):
            raise ValueError("SQL context source types changed.")
        sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
        result.append((table, rows, sql))
    return digest(result)


def raw(alias, columns):
    # BLOB values cannot be represented by JSON; freeze via the source trigger instead.
    fields = [f"'{column}',CASE WHEN typeof({alias}.\"{column}\")='blob' THEN NULL ELSE {alias}.\"{column}\" END" for column in columns]
    return "json_object(" + ",".join(fields) + ")"
