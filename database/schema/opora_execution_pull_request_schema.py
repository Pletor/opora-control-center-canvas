"""Additive execution -> PR links, request replay and loop-closure events (docs/oporahub-executions.md)."""
TABLES = ("opora_execution_pull_requests", "opora_execution_pull_request_requests",
          "opora_execution_pull_request_events")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_execution_pull_requests(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 node_id TEXT NOT NULL, accepted_revision TEXT NOT NULL, repository TEXT NOT NULL,
 number INTEGER NOT NULL, head_ref TEXT NOT NULL, head_sha TEXT NOT NULL, state TEXT NOT NULL,
 binding_id TEXT, enrollment TEXT NOT NULL, enrollment_error TEXT, enrollment_retry_at REAL,
 enrollment_failures INTEGER NOT NULL DEFAULT 0, merge_sha TEXT, merged_at TEXT,
 awaiting_human_close INTEGER NOT NULL DEFAULT 0, attention TEXT, source TEXT NOT NULL,
 linked_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id));
CREATE INDEX IF NOT EXISTS opora_execution_pull_requests_pr
 ON opora_execution_pull_requests(project_id,workspace_id,repository,number);
CREATE TABLE IF NOT EXISTS opora_execution_pull_request_requests(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, request_id TEXT NOT NULL,
 execution_id TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,request_id));
CREATE TABLE IF NOT EXISTS opora_execution_pull_request_events(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, event_key TEXT NOT NULL,
 execution_id TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,event_key));
"""
