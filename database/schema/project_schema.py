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
-- backend/memory/memory_service.py: nastavení platné pro celou aplikaci (nikdy per projekt).
CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- backend/canvas/activity_log.py: záznam činnosti člověka a agentů (docs/zaznam-cinnosti.md).
CREATE TABLE IF NOT EXISTS activity_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, agent TEXT NOT NULL,
  method TEXT NOT NULL, path TEXT NOT NULL, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
  node_ids TEXT NOT NULL, status INTEGER NOT NULL, summary TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS activity_log_scope ON activity_log(project_id, workspace_id, actor, id);
"""

# projects/<id>/project.sqlite – vše o jednom projektu; vlastník tabulky v komentáři.
PROJECT_SCHEMA = """
-- backend/canvas/canvas_service.py: graf plátna ne-git projektu
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, graph TEXT);
-- backend/canvas/project_architecture.py: architektura projektu (domény, stránky, sektory mezi nimi), jedna nad všemi worktree;
-- removed = ID uzlů a hran, které architektura smazala (skryjí se i ve starých kopiích grafu)
CREATE TABLE IF NOT EXISTS project_architecture(
    project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, graph TEXT NOT NULL,
    updated_at TEXT NOT NULL, actor TEXT NOT NULL, removed TEXT NOT NULL);
-- backend/canvas/project_architecture.py: historie a návrat architektury; jen přibývají revize
CREATE TABLE IF NOT EXISTS project_architecture_revisions(
    project_id TEXT NOT NULL, revision INTEGER NOT NULL, graph TEXT NOT NULL, actor TEXT NOT NULL,
    workspace TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(project_id, revision));
-- backend/project_setup/project_hub.py: cíl a platforma projektu
CREATE TABLE IF NOT EXISTS project_settings(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, goal TEXT NOT NULL, platform TEXT NOT NULL);
-- backend/project_setup/project_hub.py: profil projektu (architektura, uživatelé); revizi nese project_settings
CREATE TABLE IF NOT EXISTS project_profile(project_id TEXT PRIMARY KEY, architecture TEXT NOT NULL, tenancy TEXT NOT NULL);
-- backend/editor/node/node_text.py
CREATE TABLE IF NOT EXISTS node_text_revisions(
    project_id TEXT, workspace_id TEXT, node_id TEXT, revision INTEGER,
    text TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,node_id,revision));
-- backend/editor/brief_vault/brief_vault.py: schránka zadání; doslovné fragmenty, jen přibývají revize
CREATE TABLE IF NOT EXISTS brief_fragment_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, fragment_id TEXT NOT NULL, revision INTEGER NOT NULL,
    parent_id TEXT, scope_node_id TEXT, ord INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
    text TEXT NOT NULL, stage TEXT NOT NULL, mvp TEXT NOT NULL, note TEXT NOT NULL, by TEXT NOT NULL,
    actor TEXT NOT NULL, deleted INTEGER NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, fragment_id, revision));
-- backend/editor/brief_vault/brief_vault_details.py: výzkum, otázka a odkazy na rozhodnutí fragmentu (JSON, jen přibývají revize)
CREATE TABLE IF NOT EXISTS brief_fragment_details(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, fragment_id TEXT NOT NULL, revision INTEGER NOT NULL,
    fields TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, fragment_id, revision));
-- backend/editor/brief_vault/brief_vault_details.py: zpětná vazba člověka k fragmentu (append-only)
CREATE TABLE IF NOT EXISTS brief_fragment_feedback(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, fragment_id TEXT NOT NULL,
    fragment_revision INTEGER NOT NULL, verdict TEXT NOT NULL, text TEXT NOT NULL, by TEXT NOT NULL,
    actor TEXT NOT NULL, at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
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
-- backend/editor/node/drawing_files.py: obrázky kresby (scéna nese jen fileId), sdílené vrstvami projektu
CREATE TABLE IF NOT EXISTS drawing_files(
    project_id TEXT NOT NULL, file_id TEXT NOT NULL, mime_type TEXT NOT NULL,
    data BLOB NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, file_id));
-- backend/editor/node/removals.py
CREATE TABLE IF NOT EXISTS graph_recoveries(
    id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT,
    graph TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/editor/node/removal_recovery.py: jednorázový záznam obnovy smazaného obsahu (id = graph_recoveries.id)
CREATE TABLE IF NOT EXISTS removal_restores(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    record TEXT NOT NULL, created_at TEXT NOT NULL, used_at TEXT);
-- backend/editor/canvas_versions/canvas_versions.py: uložené verze plátna (graf + stav Desktop v3)
CREATE TABLE IF NOT EXISTS canvas_versions(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    author TEXT NOT NULL, created_at TEXT NOT NULL, graph TEXT NOT NULL, state TEXT NOT NULL,
    graph_digest TEXT NOT NULL, state_digest TEXT NOT NULL,
    snapshot TEXT, content_digest TEXT);
CREATE INDEX IF NOT EXISTS canvas_versions_scope
    ON canvas_versions(project_id, workspace_id, created_at DESC);
-- Index canvas_versions_content (dotaz „je obsah už uložený“) vzniká v ensure_canvas_version_columns:
-- starší tabulka sloupec content_digest v tuto chvíli ještě nemá.
-- backend/editor/agent_memory/desktop_v3_state.py
CREATE TABLE IF NOT EXISTS desktop_v3_state(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, revision INTEGER NOT NULL,
    state TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(project_id, workspace_id));
-- backend/editor/agent_memory/agent_workspace.py
CREATE TABLE IF NOT EXISTS agent_workspace_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    revision INTEGER NOT NULL, sections TEXT NOT NULL, by TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, revision));
-- backend/editor/agent_packet/desktop_v3_packets.py
CREATE TABLE IF NOT EXISTS desktop_v3_snapshots(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, digest TEXT NOT NULL, request TEXT NOT NULL,
    packet TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/editor/agent_memory/agent_results.py: immutable original outputs and their specification
CREATE TABLE IF NOT EXISTS assignment_snapshots(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS card_leases(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    owner TEXT NOT NULL, token TEXT NOT NULL, expires_at REAL NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id));
CREATE TABLE IF NOT EXISTS card_work_activity(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    agent TEXT NOT NULL, started_at TEXT, updated_at TEXT NOT NULL, touched TEXT,
    PRIMARY KEY(project_id, workspace_id, node_id));
CREATE TABLE IF NOT EXISTS port_spawns(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    block_id TEXT NOT NULL, port_id TEXT NOT NULL, target_id TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, block_id, port_id));
-- backend/editor/agent_memory/card_rounds.py: zamrazená kola karty (v1, v2, …); jen přibývají revize
CREATE TABLE IF NOT EXISTS card_rounds(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL, round INTEGER NOT NULL,
    revision INTEGER NOT NULL, record TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, round, revision));
CREATE INDEX IF NOT EXISTS assignment_snapshots_scope
    ON assignment_snapshots(project_id, workspace_id, node_id, sequence DESC);
CREATE TABLE IF NOT EXISTS agent_result_records(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    record TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS agent_results_scope
    ON agent_result_records(project_id, workspace_id, node_id, sequence DESC);
-- backend/project/workspace/workspace_documents.py
CREATE TABLE IF NOT EXISTS workspace_documents(
    project TEXT NOT NULL, workspace TEXT NOT NULL, path TEXT NOT NULL,
    revision INTEGER NOT NULL, fields TEXT NOT NULL, node_id TEXT,
    source_version TEXT, saved_at TEXT NOT NULL,
    PRIMARY KEY(project, workspace, path));
-- backend/editor/agent_handoff/message_store.py: neměnné adresované zprávy a jedno potvrzení adresáta.
CREATE TABLE IF NOT EXISTS agent_messages(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL,
    kind TEXT NOT NULL, body TEXT NOT NULL, reply_to_message_id TEXT,
    idempotency_key TEXT NOT NULL, sender_label TEXT NOT NULL, created_at TEXT NOT NULL,
    digest TEXT NOT NULL, content_digest TEXT NOT NULL,
    UNIQUE(project_id, workspace_id, source_node_id, idempotency_key));
CREATE INDEX IF NOT EXISTS agent_messages_scope_incoming
    ON agent_messages(project_id, workspace_id, target_node_id, sequence DESC);
CREATE INDEX IF NOT EXISTS agent_messages_scope_outgoing
    ON agent_messages(project_id, workspace_id, source_node_id, sequence DESC);
CREATE TABLE IF NOT EXISTS agent_message_receipts(
    message_id TEXT PRIMARY KEY, disposition TEXT NOT NULL, note TEXT NOT NULL,
    recipient_label TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/canvas/check_runs.py: zaznamenaný výsledek kontrol k jednomu commitu; aplikace testy nespouští
CREATE TABLE IF NOT EXISTS check_runs(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, scope_id TEXT NOT NULL,
    sha TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, recorded_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, scope_id, sha, recorded_at));
-- backend/canvas/opora_hub.py: index commitů OporaHubu; pravda leží v souborech oporahub/<id>.json
CREATE TABLE IF NOT EXISTS opora_commits(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, scope_id TEXT NOT NULL,
    id TEXT NOT NULL, parent TEXT, scope_kind TEXT NOT NULL, spec_revision INTEGER NOT NULL,
    subject TEXT NOT NULL, author_kind TEXT NOT NULL, author_name TEXT NOT NULL,
    created_at TEXT NOT NULL, in_main INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, workspace_id, id));
CREATE INDEX IF NOT EXISTS opora_commits_scope
    ON opora_commits(project_id, workspace_id, scope_id, created_at);
"""

# Tabulky staré centrální canvas.sqlite, které patří jednomu projektu, a sloupec s jeho ID.
PROJECT_TABLES = {
    "drafts": "id",
    "project_settings": "project_id",
    "node_text_revisions": "project_id",
    "brief_fragment_revisions": "project_id",
    "brief_fragment_details": "project_id",
    "brief_fragment_feedback": "project_id",
    "node_spec_revisions": "project_id",
    "node_journal_revisions": "project_id",
    "drawing_revisions": "project_id",
    "drawing_files": "project_id",
    "graph_recoveries": "project_id",
    "canvas_versions": "project_id",
    "desktop_v3_state": "project_id",
    "desktop_v3_snapshots": "project_id",
    "workspace_documents": "project",
    "check_runs": "project_id",
    "opora_commits": "project_id",
}
REGISTRY_TABLES = ("projects", "project_sources", "builtin_project_metadata", "workspaces", "jobs", "archived_projects")


# CanvasVersions._dirty hledá verzi se stejným obsahem; bez indexu prochází všechny ~5MB řádky (karta P1).
CANVAS_VERSIONS_CONTENT_INDEX = """
CREATE INDEX IF NOT EXISTS canvas_versions_content
    ON canvas_versions(project_id, workspace_id, content_digest);
"""


def ensure_canvas_version_columns(db):
    """Add full snapshot columns; existing graph/state versions remain explicitly partial."""
    columns = {row[1] for row in db.execute("PRAGMA table_info(canvas_versions)")}
    for name in ("snapshot", "content_digest"):
        if name not in columns:
            db.execute(f"ALTER TABLE canvas_versions ADD COLUMN {name} TEXT")
    if {"project_id", "workspace_id"} <= columns:
        db.execute(CANVAS_VERSIONS_CONTENT_INDEX)
