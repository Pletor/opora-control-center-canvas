"""Additive tables for verified human reviewers, incidents, reverts, eval cases and promoted checks.

Contract: docs/oporahub-review-identity.md. Identities, reverts and promotions are project-wide
(a person and a bug class span every card workspace); incidents and eval cases keep the workspace
of the reviewed PR for traceability. Eval cases are immutable once created."""
TABLES = ("opora_review_identities", "opora_review_incidents", "opora_review_reverts",
          "opora_review_eval_cases", "opora_review_promotions")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_review_identities(
 project_id TEXT NOT NULL, identity_id TEXT NOT NULL, name TEXT NOT NULL, github_login TEXT NOT NULL,
 github_user_id INTEGER, state TEXT NOT NULL, operator INTEGER NOT NULL DEFAULT 0, nonce TEXT NOT NULL,
 claimed_at TEXT NOT NULL, verified_at TEXT, revoked_at TEXT, evidence TEXT,
 PRIMARY KEY(project_id,identity_id));
CREATE UNIQUE INDEX IF NOT EXISTS opora_review_identity_user
 ON opora_review_identities(project_id,github_user_id) WHERE state='verified';
CREATE TABLE IF NOT EXISTS opora_review_incidents(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, incident_id TEXT NOT NULL, repository TEXT NOT NULL,
 number INTEGER NOT NULL, reference TEXT NOT NULL, summary TEXT NOT NULL, by TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,incident_id), UNIQUE(project_id,repository,number,reference));
CREATE TABLE IF NOT EXISTS opora_review_reverts(
 project_id TEXT NOT NULL, repository TEXT NOT NULL, number INTEGER NOT NULL, revert_number INTEGER NOT NULL,
 revert_sha TEXT NOT NULL, observed_at TEXT NOT NULL,
 PRIMARY KEY(project_id,repository,number,revert_number));
CREATE TABLE IF NOT EXISTS opora_review_eval_cases(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, case_id TEXT NOT NULL, repository TEXT NOT NULL,
 number INTEGER NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,case_id), UNIQUE(project_id,repository,number,kind,source));
CREATE TABLE IF NOT EXISTS opora_review_promotions(
 project_id TEXT NOT NULL, bug_class TEXT NOT NULL, check_ref TEXT NOT NULL, by TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(project_id,bug_class));
"""
