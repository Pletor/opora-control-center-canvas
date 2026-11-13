"""Additive immutable graph proposals/manifests; accepted refs remain shared with specs."""
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_graph_proposals(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
 parent_revision TEXT, created_at TEXT NOT NULL, content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id));
-- Nástupce návrhu (lineage_status) se hledá podle `supersedes`; bez indexu každé hledání parsovalo všechny návrhy
-- a agent-state Ample tak 25 s držel zámek projektu (OP-A3AE94).
CREATE INDEX IF NOT EXISTS opora_graph_proposals_supersedes
 ON opora_graph_proposals(project_id, workspace_id, json_extract(content, '$.supersedes'));
CREATE TABLE IF NOT EXISTS opora_graph_manifests(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id));
"""
