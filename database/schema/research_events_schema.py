"""Durable research invalidations in the same database as graph revisions."""
TABLES = ("research_events",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_events (
 cursor INTEGER PRIMARY KEY AUTOINCREMENT,
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, batch_key TEXT NOT NULL,
 payload TEXT NOT NULL,
 UNIQUE(project_id, workspace_id, batch_key)
);
CREATE INDEX IF NOT EXISTS research_events_scope
 ON research_events(project_id, workspace_id, cursor);
"""
