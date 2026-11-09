"""Native storyboard working history; acceptance remains in existing content manifests."""
TABLES = ("storyboard_revisions",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS storyboard_revisions(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>=0), record TEXT,
 PRIMARY KEY(project_id,workspace_id,node_id,revision));
CREATE TRIGGER IF NOT EXISTS storyboard_revisions_update BEFORE UPDATE ON storyboard_revisions
BEGIN SELECT RAISE(ABORT, 'Immutable storyboard revision'); END;
CREATE TRIGGER IF NOT EXISTS storyboard_revisions_delete BEFORE DELETE ON storyboard_revisions
BEGIN SELECT RAISE(ABORT, 'Immutable storyboard revision'); END;
CREATE TRIGGER IF NOT EXISTS storyboard_revisions_replace BEFORE INSERT ON storyboard_revisions
WHEN EXISTS(SELECT 1 FROM storyboard_revisions WHERE project_id=NEW.project_id
 AND workspace_id=NEW.workspace_id AND node_id=NEW.node_id AND revision=NEW.revision)
BEGIN SELECT RAISE(ABORT, 'Immutable storyboard revision'); END;
"""
