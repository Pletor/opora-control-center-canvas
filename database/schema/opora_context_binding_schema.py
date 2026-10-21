"""Registry-only monotonic source/lifecycle fence; no project content history."""

SCHEMA = """CREATE TABLE IF NOT EXISTS opora_context_bindings(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, identity TEXT NOT NULL,
 generation INTEGER NOT NULL DEFAULT 0, schema_digest TEXT NOT NULL,
 trigger_digest TEXT NOT NULL, schema_version INTEGER NOT NULL, frozen TEXT,
 PRIMARY KEY(project_id,workspace_id))"""
