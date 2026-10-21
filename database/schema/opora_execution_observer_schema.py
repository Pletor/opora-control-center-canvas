"""Immutable independent observer evidence, plus a global billing-session fence."""
TABLES = ("opora_execution_intents", "opora_execution_observations", "opora_execution_observation_refs")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_execution_intents(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,id TEXT PRIMARY KEY,
 execution_id TEXT NOT NULL,request_id TEXT NOT NULL,content TEXT NOT NULL,
 UNIQUE(project_id,workspace_id,execution_id),UNIQUE(project_id,workspace_id,request_id));
CREATE TABLE IF NOT EXISTS opora_execution_observations(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,id TEXT PRIMARY KEY,
 intent_id TEXT NOT NULL,parent_id TEXT,request_id TEXT NOT NULL,sequence INTEGER NOT NULL,content TEXT NOT NULL,
 UNIQUE(intent_id,request_id),UNIQUE(intent_id,sequence));
CREATE TABLE IF NOT EXISTS opora_execution_observation_refs(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,intent_id TEXT PRIMARY KEY,head_id TEXT NOT NULL);
"""
REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_execution_observer_sessions(
 provider TEXT NOT NULL,session_id TEXT NOT NULL,project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,
 intent_id TEXT NOT NULL,content TEXT NOT NULL,PRIMARY KEY(provider,session_id),UNIQUE(intent_id));
"""


def immutable(table, match):
    return f"""
CREATE TRIGGER IF NOT EXISTS {table}_update BEFORE UPDATE ON {table}
BEGIN SELECT RAISE(ABORT,'Immutable observer evidence'); END;
CREATE TRIGGER IF NOT EXISTS {table}_delete BEFORE DELETE ON {table}
BEGIN SELECT RAISE(ABORT,'Immutable observer evidence'); END;
CREATE TRIGGER IF NOT EXISTS {table}_replace BEFORE INSERT ON {table}
WHEN EXISTS(SELECT 1 FROM {table} WHERE {match})
BEGIN SELECT RAISE(ABORT,'Immutable observer evidence'); END;
"""


SCHEMA += immutable(TABLES[0], "id=NEW.id OR (project_id=NEW.project_id AND workspace_id=NEW.workspace_id AND (request_id=NEW.request_id OR execution_id=NEW.execution_id))")
SCHEMA += immutable(TABLES[1], "id=NEW.id OR (intent_id=NEW.intent_id AND (request_id=NEW.request_id OR sequence=NEW.sequence))")
REGISTRY_SCHEMA += immutable("opora_execution_observer_sessions", "(provider=NEW.provider AND session_id=NEW.session_id) OR intent_id=NEW.intent_id")
SCHEMA += """
CREATE TRIGGER IF NOT EXISTS opora_execution_observation_refs_delete BEFORE DELETE ON opora_execution_observation_refs
BEGIN SELECT RAISE(ABORT,'Observer head cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS opora_execution_observation_refs_replace BEFORE INSERT ON opora_execution_observation_refs
WHEN EXISTS(SELECT 1 FROM opora_execution_observation_refs WHERE intent_id=NEW.intent_id)
BEGIN SELECT RAISE(ABORT,'Observer head cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS opora_execution_observation_refs_insert BEFORE INSERT ON opora_execution_observation_refs
WHEN NOT EXISTS(SELECT 1 FROM opora_execution_observations r WHERE r.id=NEW.head_id
 AND r.intent_id=NEW.intent_id AND r.project_id=NEW.project_id AND r.workspace_id=NEW.workspace_id AND r.parent_id IS NULL)
BEGIN SELECT RAISE(ABORT,'Observer head must start at its scoped root'); END;
CREATE TRIGGER IF NOT EXISTS opora_execution_observation_refs_update BEFORE UPDATE ON opora_execution_observation_refs
WHEN NEW.project_id IS NOT OLD.project_id OR NEW.workspace_id IS NOT OLD.workspace_id
 OR NEW.intent_id IS NOT OLD.intent_id OR (NEW.head_id IS NOT OLD.head_id AND NOT EXISTS(
 SELECT 1 FROM opora_execution_observations r WHERE r.id=NEW.head_id AND r.intent_id=OLD.intent_id
 AND r.project_id=OLD.project_id AND r.workspace_id=OLD.workspace_id AND r.parent_id=OLD.head_id))
BEGIN SELECT RAISE(ABORT,'Observer head must advance to its scoped child'); END;
"""
