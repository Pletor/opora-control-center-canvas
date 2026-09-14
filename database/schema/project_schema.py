"""SQL schéma po tabulkách: registr projektů (registry.sqlite) a databáze jednoho projektu (project.sqlite).

Každá tabulka má jednoho vlastníka v backendu; ten ji čte a píše, ale nevytváří. Vytváření je jen zde.
"""

# .data/<root>/registry.sqlite – jen to, co musí být vidět napříč projekty.
REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT, repo TEXT, url TEXT, branch TEXT);
CREATE TABLE IF NOT EXISTS project_sources(project_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_path TEXT);
CREATE TABLE IF NOT EXISTS builtin_project_metadata(project_id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, project_id TEXT, directory TEXT, branch TEXT, node_id TEXT, actor TEXT, base_sha TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, status TEXT, message TEXT, project_id TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS archived_projects(project_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, archived_at TEXT NOT NULL);
"""

# projects/<id>/project.sqlite – vše o jednom projektu; vlastník tabulky v komentáři.
PROJECT_SCHEMA = """
-- backend/canvas/canvas_service.py: graf plátna ne-git projektu
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, graph TEXT);
-- backend/project_setup/project_hub.py: cíl a platforma projektu
CREATE TABLE IF NOT EXISTS project_settings(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, goal TEXT NOT NULL, platform TEXT NOT NULL);
-- backend/editor/node/node_text.py
CREATE TABLE IF NOT EXISTS node_text_revisions(
    project_id TEXT, workspace_id TEXT, node_id TEXT, revision INTEGER,
    text TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,node_id,revision));
-- backend/editor/node/node_specs.py
CREATE TABLE IF NOT EXISTS node_spec_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    revision INTEGER NOT NULL, fields TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, revision));
-- backend/editor/node/node_journal.py
CREATE TABLE IF NOT EXISTS node_journal_revisions(
    project_id TEXT, workspace_id TEXT, node_id TEXT, day TEXT, revision INTEGER,
    text TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,node_id,day,revision));
-- backend/editor/node/drawings.py
CREATE TABLE IF NOT EXISTS drawing_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, layer_id TEXT NOT NULL,
    revision INTEGER NOT NULL, scene TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, layer_id, revision));
-- backend/editor/node/removals.py
CREATE TABLE IF NOT EXISTS graph_recoveries(
    id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT,
    graph TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/editor/agent_memory/desktop_v3_state.py
CREATE TABLE IF NOT EXISTS desktop_v3_state(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, revision INTEGER NOT NULL,
    state TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(project_id, workspace_id));
-- backend/editor/agent_packet/desktop_v3_packets.py
CREATE TABLE IF NOT EXISTS desktop_v3_snapshots(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, digest TEXT NOT NULL, request TEXT NOT NULL,
    packet TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/project/workspace/workspace_documents.py
CREATE TABLE IF NOT EXISTS workspace_documents(
    project TEXT NOT NULL, workspace TEXT NOT NULL, path TEXT NOT NULL,
    revision INTEGER NOT NULL, fields TEXT NOT NULL, node_id TEXT,
    source_version TEXT, saved_at TEXT NOT NULL,
    PRIMARY KEY(project, workspace, path));
-- backend/live_run/agent_bindings.py
CREATE TABLE IF NOT EXISTS agent_bindings(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    layer TEXT NOT NULL, node_id TEXT NOT NULL, source_id TEXT NOT NULL,
    run_id TEXT NOT NULL, session_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_binding_scopes(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    revision INTEGER NOT NULL, PRIMARY KEY(project_id, workspace_id, node_id));
-- backend/live_run/agent_activity.py
CREATE TABLE IF NOT EXISTS agent_activity_entries(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, source_id TEXT NOT NULL, run_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL, source_timestamp TEXT, ingest_timestamp TEXT NOT NULL,
    kind TEXT NOT NULL, summary TEXT NOT NULL,
    author_type TEXT NOT NULL, source_trust TEXT NOT NULL,
    UNIQUE(project_id, workspace_id, node_id, source_id, run_id, source_event_id));
-- backend/live_run/node_sessions.py
CREATE TABLE IF NOT EXISTS node_sessions(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, source TEXT NOT NULL, session_id TEXT NOT NULL,
    run_id TEXT, role TEXT NOT NULL, title TEXT NOT NULL, parent_session_id TEXT,
    bound_at TEXT NOT NULL, baseline_at TEXT NOT NULL, baseline_cursor INTEGER NOT NULL,
    closed_at TEXT, closed_snapshot TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS node_sessions_active
    ON node_sessions(project_id, workspace_id, source, session_id) WHERE closed_at IS NULL;
CREATE INDEX IF NOT EXISTS node_sessions_scope ON node_sessions(project_id, workspace_id, node_id);
"""

# Tabulky staré centrální canvas.sqlite, které patří jednomu projektu, a sloupec s jeho ID.
PROJECT_TABLES = {
    "drafts": "id",
    "project_settings": "project_id",
    "node_text_revisions": "project_id",
    "node_spec_revisions": "project_id",
    "node_journal_revisions": "project_id",
    "drawing_revisions": "project_id",
    "graph_recoveries": "project_id",
    "desktop_v3_state": "project_id",
    "desktop_v3_snapshots": "project_id",
    "workspace_documents": "project",
    "agent_bindings": "project_id",
    "agent_binding_scopes": "project_id",
    "agent_activity_entries": "project_id",
    "node_sessions": "project_id",
}
REGISTRY_TABLES = ("projects", "project_sources", "builtin_project_metadata", "workspaces", "jobs", "archived_projects")
