"""Additive automated code review jobs, worker tasks, posted findings and human decisions.

Contract: docs/oporahub-review-jobs.md. One job per (PR, headSha); tasks are leased slots
(finder/voter) with their own token and monotonic epoch; findings are deduplicated per PR
by fingerprint across rounds."""
TABLES = ("opora_review_jobs", "opora_review_tasks", "opora_review_task_requests",
          "opora_review_findings", "opora_review_decisions")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_review_jobs(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, job_id TEXT NOT NULL,
 execution_id TEXT NOT NULL, node_id TEXT NOT NULL, repository TEXT NOT NULL, number INTEGER NOT NULL,
 base_sha TEXT, head_sha TEXT NOT NULL, round INTEGER NOT NULL, since_sha TEXT,
 risk_tier TEXT NOT NULL, risk TEXT NOT NULL, required_approvals INTEGER NOT NULL,
 finders INTEGER NOT NULL, voters INTEGER NOT NULL, required_votes INTEGER NOT NULL,
 phase TEXT NOT NULL, candidates TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 completed_at TEXT,
 PRIMARY KEY(project_id,workspace_id,job_id),
 UNIQUE(project_id,workspace_id,repository,number,head_sha));
CREATE TABLE IF NOT EXISTS opora_review_tasks(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL, job_id TEXT NOT NULL,
 role TEXT NOT NULL, slot INTEGER NOT NULL, state TEXT NOT NULL, owner TEXT, token TEXT,
 epoch INTEGER NOT NULL DEFAULT 0, expires_at REAL, request_id TEXT, digest TEXT, submission TEXT,
 submitted_at TEXT,
 PRIMARY KEY(project_id,workspace_id,task_id), UNIQUE(project_id,workspace_id,job_id,role,slot));
CREATE TABLE IF NOT EXISTS opora_review_task_requests(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, owner TEXT NOT NULL, request_id TEXT NOT NULL,
 digest TEXT NOT NULL, task_id TEXT,
 PRIMARY KEY(project_id,workspace_id,owner,request_id));
CREATE TABLE IF NOT EXISTS opora_review_findings(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, finding_id TEXT NOT NULL,
 repository TEXT NOT NULL, number INTEGER NOT NULL, fingerprint TEXT NOT NULL, job_id TEXT NOT NULL,
 round INTEGER NOT NULL, head_sha TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
 content TEXT NOT NULL, resolution TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,finding_id),
 UNIQUE(project_id,workspace_id,repository,number,fingerprint));
CREATE TABLE IF NOT EXISTS opora_review_decisions(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, repository TEXT NOT NULL, number INTEGER NOT NULL,
 head_sha TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL, by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,repository,number,head_sha));
"""
