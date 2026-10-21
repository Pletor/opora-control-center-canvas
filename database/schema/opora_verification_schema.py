"""Append-only formal evidence metadata and exact, content-addressed bytes."""
TABLES = ("opora_verification_requests", "opora_verification_reports", "opora_verification_blobs")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_verification_requests(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 node_id TEXT NOT NULL, execution_id TEXT NOT NULL, request_id TEXT NOT NULL,
 digest TEXT NOT NULL, record TEXT NOT NULL,
 UNIQUE(project_id,workspace_id,execution_id,request_id));
CREATE TABLE IF NOT EXISTS opora_verification_reports(
 verification_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 request_id TEXT NOT NULL, digest TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opora_verification_blobs(
 project_id TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, data BLOB NOT NULL,
 PRIMARY KEY(project_id,sha256));
"""
