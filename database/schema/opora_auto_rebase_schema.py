"""Additive Scion-style plan tables: auto-rebase outcomes, conflicts, derived history, sparse enrollment.

Contract: docs/oporahub-auto-rebase.md. Outcome rows make the rebase loop idempotent per
(proposal, accepted head); derived rows are a recomputable cache keyed by accepted revision."""
TABLES = ("opora_auto_rebase_outcomes", "opora_auto_rebase_conflicts", "opora_derived_revisions",
          "opora_derived_card_changes", "opora_sparse_enrollment", "opora_sparse_watermarks")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_auto_rebase_outcomes(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, proposal_kind TEXT NOT NULL, proposal_id TEXT NOT NULL,
 accepted_head TEXT NOT NULL, outcome TEXT NOT NULL, result_id TEXT, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,proposal_kind,proposal_id,accepted_head));
CREATE TABLE IF NOT EXISTS opora_auto_rebase_conflicts(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, proposal_kind TEXT NOT NULL,
 proposal_id TEXT NOT NULL, accepted_head TEXT NOT NULL, status TEXT NOT NULL, resolution_id TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id));
CREATE INDEX IF NOT EXISTS opora_auto_rebase_conflicts_open
 ON opora_auto_rebase_conflicts(project_id,workspace_id,status);
CREATE TABLE IF NOT EXISTS opora_derived_revisions(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, revision_id TEXT NOT NULL, parent_id TEXT,
 version INTEGER NOT NULL, PRIMARY KEY(project_id,workspace_id,revision_id));
CREATE TABLE IF NOT EXISTS opora_derived_card_changes(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, revision_id TEXT NOT NULL, card_id TEXT NOT NULL,
 content TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,revision_id,card_id));
CREATE INDEX IF NOT EXISTS opora_derived_card_changes_card
 ON opora_derived_card_changes(project_id,workspace_id,card_id);
CREATE TABLE IF NOT EXISTS opora_sparse_enrollment(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL, status TEXT NOT NULL,
 reason TEXT, accepted_revision TEXT, source TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,node_id));
CREATE TABLE IF NOT EXISTS opora_sparse_watermarks(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, accepted_head TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id));
"""
