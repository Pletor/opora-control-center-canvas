"""Additive durable reconciliation authority; project migrations retain every table."""
RECONCILIATION_TABLES = ("opora_reconciliation_records", "opora_reconciliation_refs", "opora_reconciliation_requests")
RECONCILIATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_reconciliation_records(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
 kind TEXT NOT NULL, binding_id TEXT NOT NULL, created_at TEXT NOT NULL, content TEXT NOT NULL, event_key TEXT,
 PRIMARY KEY(project_id,workspace_id,id));
CREATE INDEX IF NOT EXISTS opora_reconciliation_history
 ON opora_reconciliation_records(project_id,workspace_id,binding_id,kind);
CREATE UNIQUE INDEX IF NOT EXISTS opora_reconciliation_event_key
 ON opora_reconciliation_records(project_id,workspace_id,binding_id,event_key) WHERE kind='event';
CREATE TABLE IF NOT EXISTS opora_reconciliation_refs(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, binding_id TEXT NOT NULL,
 control_id TEXT NOT NULL, generation INTEGER NOT NULL, enabled INTEGER NOT NULL,
 PRIMARY KEY(project_id,workspace_id,binding_id));
CREATE TABLE IF NOT EXISTS opora_reconciliation_requests(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, request_id TEXT NOT NULL,
 digest TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,request_id));
"""
