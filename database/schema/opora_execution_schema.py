"""Additive execution enrollment, immutable assignments, result receipts and step checkpoints."""
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_execution_epochs (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
 epoch INTEGER NOT NULL, PRIMARY KEY(project_id,workspace_id,node_id));
CREATE TABLE IF NOT EXISTS opora_executions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 node_id TEXT NOT NULL, owner TEXT NOT NULL, request_id TEXT NOT NULL,
 request_digest TEXT NOT NULL, record TEXT NOT NULL,
 UNIQUE(project_id,workspace_id,owner,request_id));
CREATE TABLE IF NOT EXISTS opora_execution_results (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 execution_id TEXT NOT NULL, request_id TEXT NOT NULL, digest TEXT NOT NULL,
 record TEXT NOT NULL, PRIMARY KEY(execution_id,request_id));
CREATE TABLE IF NOT EXISTS opora_execution_steps (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 execution_id TEXT NOT NULL, request_id TEXT NOT NULL, step_id TEXT NOT NULL,
 digest TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(execution_id,request_id));
"""
