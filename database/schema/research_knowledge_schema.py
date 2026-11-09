"""Append-only context references; source payloads remain in their original project."""
TABLES = ("research_scope_bindings",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_scope_bindings (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, scope_node_id TEXT NOT NULL,
 id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision > 0), payload TEXT NOT NULL,
 PRIMARY KEY(project_id, workspace_id, id, revision));
"""
