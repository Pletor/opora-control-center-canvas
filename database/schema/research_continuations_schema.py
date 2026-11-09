"""Additive receipts; old research revisions and native flow runs remain authoritative."""
TABLES = ("research_continuations",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_continuations(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
 research_id TEXT NOT NULL, research_revision INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id), UNIQUE(project_id,workspace_id,research_id,research_revision));
"""
