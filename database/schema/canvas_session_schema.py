"""Additive private agent view state; never shared Canvas geometry."""
TABLES = ("canvas_session_views",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS canvas_session_views (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, session_id TEXT NOT NULL,
 revision INTEGER NOT NULL, state TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,session_id)
);
"""
