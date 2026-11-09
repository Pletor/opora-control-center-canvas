"""Additive pending human review preparation; existing accepted reviews remain unchanged."""
TABLES = ("research_review_proposals",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_review_proposals (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
 request_id TEXT NOT NULL, request_json TEXT NOT NULL, decision_id TEXT NOT NULL,
 payload TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id),
 UNIQUE(project_id,workspace_id,request_id)
);
"""
