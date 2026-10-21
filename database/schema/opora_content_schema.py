"""Immutable proposal and accepted manifest content ledgers."""
TABLES = ("opora_content_proposals", "opora_content_manifests")
SCHEMA = ""
for table in TABLES:
    SCHEMA += f"""
CREATE TABLE IF NOT EXISTS {table}(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, content TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,id));
CREATE TRIGGER IF NOT EXISTS {table}_update BEFORE UPDATE ON {table}
BEGIN SELECT RAISE(ABORT, 'Immutable content record'); END;
CREATE TRIGGER IF NOT EXISTS {table}_delete BEFORE DELETE ON {table}
BEGIN SELECT RAISE(ABORT, 'Immutable content record'); END;
CREATE TRIGGER IF NOT EXISTS {table}_replace BEFORE INSERT ON {table}
WHEN EXISTS(SELECT 1 FROM {table}
    WHERE project_id=NEW.project_id AND workspace_id=NEW.workspace_id AND id=NEW.id)
BEGIN SELECT RAISE(ABORT, 'Immutable content record'); END;
"""
