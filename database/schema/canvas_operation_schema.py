"""Additive receipts for native Canvas writes; old callers and old readers remain valid."""
TABLES = ("canvas_operation_receipts",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS canvas_operation_receipts(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, operation_kind TEXT NOT NULL,
 operation_id TEXT NOT NULL, author TEXT NOT NULL, request_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','complete')), response TEXT,
 PRIMARY KEY(project_id,workspace_id,operation_kind,operation_id)
);
"""
