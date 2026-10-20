"""Opt-in workspace content graph authority; existing file-backed workspaces stay unchanged."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_graph_authority (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=1),
 graph TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id));
"""
