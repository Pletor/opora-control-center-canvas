"""Private context origins and project secrets; neither belongs in public execution JSON."""

TABLES = ("opora_execution_context_keys", "opora_execution_context_pins")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_execution_context_keys(
    project_id TEXT PRIMARY KEY, secret TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opora_execution_context_pins(
    execution_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    pin_json TEXT NOT NULL, pin_digest TEXT NOT NULL, proof_json TEXT);
CREATE INDEX IF NOT EXISTS opora_execution_context_scope
    ON opora_execution_context_pins(project_id, workspace_id);
CREATE TRIGGER IF NOT EXISTS opora_private_context_key_update
BEFORE UPDATE ON opora_execution_context_keys BEGIN
    SELECT RAISE(ABORT, 'Immutable context key'); END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_key_delete
BEFORE DELETE ON opora_execution_context_keys BEGIN
    SELECT RAISE(ABORT, 'Immutable context key'); END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_key_replace
BEFORE INSERT ON opora_execution_context_keys
WHEN EXISTS(SELECT 1 FROM opora_execution_context_keys WHERE project_id=NEW.project_id)
BEGIN SELECT RAISE(ABORT, 'Immutable context key'); END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_pin_update
BEFORE UPDATE ON opora_execution_context_pins
WHEN NEW.execution_id IS NOT OLD.execution_id OR NEW.project_id IS NOT OLD.project_id
 OR NEW.workspace_id IS NOT OLD.workspace_id OR NEW.pin_json IS NOT OLD.pin_json
 OR NEW.pin_digest IS NOT OLD.pin_digest
BEGIN SELECT RAISE(ABORT, 'Immutable context origin'); END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_pin_delete
BEFORE DELETE ON opora_execution_context_pins BEGIN
    SELECT RAISE(ABORT, 'Immutable context origin'); END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_pin_replace
BEFORE INSERT ON opora_execution_context_pins
WHEN EXISTS(SELECT 1 FROM opora_execution_context_pins WHERE execution_id=NEW.execution_id)
BEGIN SELECT RAISE(ABORT, 'Immutable context origin'); END;
-- Explicit context preparation permanently enrolls accepted references in forward-only history.
CREATE TRIGGER IF NOT EXISTS opora_private_context_ref_update
BEFORE UPDATE ON opora_spec_refs
WHEN EXISTS(SELECT 1 FROM opora_execution_context_keys WHERE project_id IN (OLD.project_id,NEW.project_id))
BEGIN
    SELECT CASE WHEN NEW.project_id IS NOT OLD.project_id OR NEW.workspace_id IS NOT OLD.workspace_id
        THEN RAISE(ABORT, 'Context accepted reference identity is immutable') END;
    SELECT CASE WHEN NEW.accepted_id IS NOT OLD.accepted_id AND NOT EXISTS(
        SELECT 1 FROM opora_spec_revisions r
        WHERE r.project_id=OLD.project_id AND r.workspace_id=OLD.workspace_id AND r.id=NEW.accepted_id
          AND r.parent_id=OLD.accepted_id AND json_valid(r.content)
          AND json_extract(r.content,'$.id')=NEW.accepted_id
          AND json_extract(r.content,'$.project')=OLD.project_id
          AND json_extract(r.content,'$.workspace')=OLD.workspace_id
          AND json_extract(r.content,'$.parentRevision')=OLD.accepted_id
          AND json_extract(r.content,'$.kind') IN ('acceptance','graph-acceptance'))
        THEN RAISE(ABORT, 'Context accepted reference must advance to its scoped child') END;
END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_ref_delete
BEFORE DELETE ON opora_spec_refs
WHEN EXISTS(SELECT 1 FROM opora_execution_context_keys WHERE project_id=OLD.project_id)
BEGIN SELECT RAISE(ABORT, 'Context accepted reference cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS opora_private_context_ref_insert
BEFORE INSERT ON opora_spec_refs
WHEN EXISTS(SELECT 1 FROM opora_execution_context_keys WHERE project_id=NEW.project_id)
BEGIN
    SELECT CASE WHEN EXISTS(SELECT 1 FROM opora_spec_refs
        WHERE project_id=NEW.project_id AND workspace_id=NEW.workspace_id)
        THEN RAISE(ABORT, 'Context accepted reference cannot be replaced') END;
    SELECT CASE WHEN NOT EXISTS(
        SELECT 1 FROM opora_spec_revisions r
        WHERE r.project_id=NEW.project_id AND r.workspace_id=NEW.workspace_id AND r.id=NEW.accepted_id
          AND r.parent_id IS NULL AND json_valid(r.content)
          AND json_extract(r.content,'$.id')=NEW.accepted_id
          AND json_extract(r.content,'$.project')=NEW.project_id
          AND json_extract(r.content,'$.workspace')=NEW.workspace_id
          AND json_type(r.content,'$.parentRevision')='null'
          AND json_extract(r.content,'$.kind') IN ('baseline','graph-baseline'))
        THEN RAISE(ABORT, 'Context accepted reference must begin at its scoped root') END;
END;
"""
