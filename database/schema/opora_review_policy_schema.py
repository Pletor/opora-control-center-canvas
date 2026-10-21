"""Additive immutable policy history and durable, ordered GitHub observation attempts."""
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_review_policies (
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
    parent_id TEXT, created_at TEXT NOT NULL, content TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,id)
);
CREATE TABLE IF NOT EXISTS opora_review_policy_refs (
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, policy_id TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id)
);
CREATE TABLE IF NOT EXISTS opora_review_attempts (
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, sequence INTEGER NOT NULL,
    pr_number INTEGER NOT NULL, configured_repository TEXT NOT NULL, configured_branch TEXT NOT NULL,
    accepted_revision TEXT NOT NULL, policy_revision TEXT, started_at TEXT NOT NULL,
    finished_at TEXT, state TEXT NOT NULL, evidence_id TEXT, error_code TEXT,
    PRIMARY KEY(project_id,workspace_id,sequence)
);
CREATE INDEX IF NOT EXISTS opora_review_attempt_lookup ON opora_review_attempts
    (project_id,workspace_id,pr_number,configured_repository,configured_branch,sequence DESC);
"""
