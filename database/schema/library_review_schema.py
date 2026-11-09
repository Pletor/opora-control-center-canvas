"""Additive review/receipt storage for native shared-library administrative operations."""
TABLES = ("flow_library_reviews",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_library_reviews(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 request_id TEXT NOT NULL, author TEXT NOT NULL, request_hash TEXT NOT NULL,
 content TEXT NOT NULL, status TEXT NOT NULL, result TEXT,
 UNIQUE(project_id,workspace_id,author,request_id));
"""
