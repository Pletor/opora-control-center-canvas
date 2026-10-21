"""Scoped acceptance policies, immutable proposal discussions and acceptance receipts."""
RECORD_TABLES = ("opora_acceptance_policies", "opora_proposal_review_events", "opora_acceptance_receipts")
TABLES = (*RECORD_TABLES, "opora_acceptance_policy_refs", "opora_proposal_review_refs")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_acceptance_policies(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, parent_id TEXT,
 content TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,id));
CREATE TABLE IF NOT EXISTS opora_acceptance_policy_refs(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, policy_id TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id));
CREATE TABLE IF NOT EXISTS opora_proposal_review_events(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, proposal_kind TEXT NOT NULL, proposal_id TEXT NOT NULL,
 id TEXT NOT NULL, parent_id TEXT, idempotency_key TEXT NOT NULL, content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,proposal_kind,proposal_id,id),
 UNIQUE(project_id,workspace_id,proposal_kind,proposal_id,idempotency_key));
CREATE TABLE IF NOT EXISTS opora_proposal_review_refs(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, proposal_kind TEXT NOT NULL, proposal_id TEXT NOT NULL,
 head_id TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,proposal_kind,proposal_id));
CREATE TABLE IF NOT EXISTS opora_acceptance_receipts(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, accepted_revision TEXT NOT NULL,
 id TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,accepted_revision),
 UNIQUE(project_id,workspace_id,id));
"""
for table in RECORD_TABLES:
    keys = ("project_id", "workspace_id", "accepted_revision") if table.endswith("receipts") else (
        ("project_id", "workspace_id", "proposal_kind", "proposal_id", "id") if table.endswith("events") else ("project_id", "workspace_id", "id"))
    match = " AND ".join(f"{key}=NEW.{key}" for key in keys)
    if table.endswith("events"):
        match = "project_id=NEW.project_id AND workspace_id=NEW.workspace_id AND proposal_kind=NEW.proposal_kind AND proposal_id=NEW.proposal_id AND (id=NEW.id OR idempotency_key=NEW.idempotency_key)"
    elif table.endswith("receipts"):
        match = "project_id=NEW.project_id AND workspace_id=NEW.workspace_id AND (accepted_revision=NEW.accepted_revision OR id=NEW.id)"
    SCHEMA += f"""
CREATE TRIGGER IF NOT EXISTS {table}_update BEFORE UPDATE ON {table}
BEGIN SELECT RAISE(ABORT, 'Immutable proposal review record'); END;
CREATE TRIGGER IF NOT EXISTS {table}_delete BEFORE DELETE ON {table}
BEGIN SELECT RAISE(ABORT, 'Immutable proposal review record'); END;
CREATE TRIGGER IF NOT EXISTS {table}_replace BEFORE INSERT ON {table}
WHEN EXISTS(SELECT 1 FROM {table} WHERE {match})
BEGIN SELECT RAISE(ABORT, 'Immutable proposal review record'); END;
"""
for refs, records, head, fields in (
    ("opora_acceptance_policy_refs", "opora_acceptance_policies", "policy_id", ("project_id", "workspace_id")),
    ("opora_proposal_review_refs", "opora_proposal_review_events", "head_id", ("project_id", "workspace_id", "proposal_kind", "proposal_id")),
):
    moved = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in fields)
    scoped = " AND ".join(f"r.{field}=OLD.{field}" for field in fields)
    existing = " AND ".join(f"{field}=NEW.{field}" for field in fields)
    SCHEMA += f"""
CREATE TRIGGER IF NOT EXISTS {refs}_delete BEFORE DELETE ON {refs}
BEGIN SELECT RAISE(ABORT, 'Proposal review reference cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS {refs}_replace BEFORE INSERT ON {refs}
WHEN EXISTS(SELECT 1 FROM {refs} WHERE {existing})
BEGIN SELECT RAISE(ABORT, 'Proposal review reference cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS {refs}_update BEFORE UPDATE ON {refs}
WHEN {moved} OR (NEW.{head} IS NOT OLD.{head} AND NOT EXISTS(
 SELECT 1 FROM {records} r WHERE {scoped} AND r.id=NEW.{head} AND r.parent_id=OLD.{head}))
BEGIN SELECT RAISE(ABORT, 'Proposal review reference must advance to its scoped child'); END;
"""
