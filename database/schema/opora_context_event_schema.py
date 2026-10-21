"""Opt-in raw SQL transition evidence, never a sparse semantic authority."""
# Registered imports copy events before their counter authority, so installed
# event_counter triggers cannot add imported bytes to an already complete counter.
TABLES = ("opora_context_events", "opora_context_coverage")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_context_coverage(
 project_id TEXT PRIMARY KEY, coverage_id TEXT NOT NULL,
 schema_digest TEXT NOT NULL, trigger_digest TEXT NOT NULL, schema_version INTEGER NOT NULL,
 sequence INTEGER NOT NULL DEFAULT 0, bytes INTEGER NOT NULL DEFAULT 0,
 frozen TEXT);
CREATE TABLE IF NOT EXISTS opora_context_events(
 project_id TEXT NOT NULL, sequence INTEGER NOT NULL, coverage_id TEXT NOT NULL,
 source_table TEXT NOT NULL, operation TEXT NOT NULL,
 before_json TEXT, after_json TEXT, bytes INTEGER NOT NULL,
 PRIMARY KEY(project_id,sequence));
"""
