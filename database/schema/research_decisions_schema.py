"""Research decision review and native proposal receipts; no parallel task authority."""
TABLES = ("research_decision_reviews", "research_materializations")
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_decision_reviews (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
 decision_id TEXT NOT NULL, decision_revision INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id),
 UNIQUE(project_id,workspace_id,decision_id,decision_revision)
);
CREATE TABLE IF NOT EXISTS research_materializations (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, review_id TEXT NOT NULL,
 digest TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,review_id)
);
"""
