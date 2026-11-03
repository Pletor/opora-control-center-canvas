"""Engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1) v registry.sqlite.

Workflow je sdílené (`project_id` NULL) nebo patří projektu, proto žije v registru vedle `projects`.
Verze je neměnná (mění se jen `status`), log je append-only; `flow_runs` a `flow_node_runs` jsou projekce logu.
Vlastník workflow `owner_ref` (`opora:page:<nodeId>` u `page_intent`, `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md`
§2) je na `(project_id, kind, owner_ref)` jedinečný; index zakládá `project_schema.ensure_flow_owner_ref`, protože
starší registr sloupec teprve dostane.
"""

TABLES = ("flow_workflows", "flow_workflow_versions", "flow_runs", "flow_node_runs", "flow_log_events")

SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_workflows(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('heart','page_intent','brain_workflow')),
  project_id TEXT, name TEXT NOT NULL, created_at TEXT NOT NULL, owner_ref TEXT);
CREATE TABLE IF NOT EXISTS flow_workflow_versions(
  id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES flow_workflows(id), n INTEGER NOT NULL,
  graph TEXT NOT NULL, hash TEXT NOT NULL, parent_version_id TEXT,
  status TEXT NOT NULL CHECK(status IN ('draft','candidate','active','retired')),
  eval_run_id TEXT, created_at TEXT NOT NULL, UNIQUE(workflow_id, n));
CREATE UNIQUE INDEX IF NOT EXISTS flow_one_active_version
  ON flow_workflow_versions(workflow_id) WHERE status='active';
CREATE TRIGGER IF NOT EXISTS flow_workflow_versions_frozen
  BEFORE UPDATE OF id, workflow_id, n, graph, hash, parent_version_id ON flow_workflow_versions
  BEGIN SELECT RAISE(ABORT,'Verze workflow je neměnná'); END;
CREATE TRIGGER IF NOT EXISTS flow_workflow_versions_delete BEFORE DELETE ON flow_workflow_versions
  BEGIN SELECT RAISE(ABORT,'Verze workflow je neměnná'); END;
CREATE TABLE IF NOT EXISTS flow_runs(
  id TEXT PRIMARY KEY, workflow_version_id TEXT NOT NULL REFERENCES flow_workflow_versions(id),
  trigger TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','waiting','succeeded','failed','cancelled')),
  parent_run_id TEXT, cost_usd REAL NOT NULL DEFAULT 0, tokens INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS flow_node_runs(
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES flow_runs(id), node_id TEXT NOT NULL,
  attempt INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','waiting','succeeded','failed')),
  idempotency_key TEXT NOT NULL, input_ref TEXT, output_ref TEXT, output_port TEXT, error TEXT,
  provider TEXT, model TEXT, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL,
  started_at TEXT, ended_at TEXT, last_heartbeat_at TEXT, waiting_for TEXT, deadline TEXT,
  UNIQUE(idempotency_key, attempt));
CREATE INDEX IF NOT EXISTS flow_node_runs_open ON flow_node_runs(status, run_id);
CREATE TABLE IF NOT EXISTS flow_log_events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, node_run_id TEXT, ts TEXT NOT NULL,
  type TEXT NOT NULL, payload TEXT NOT NULL, canvas INTEGER NOT NULL CHECK(canvas BETWEEN 1 AND 4));
CREATE INDEX IF NOT EXISTS flow_log_events_run ON flow_log_events(run_id, seq);
CREATE TRIGGER IF NOT EXISTS flow_log_events_update BEFORE UPDATE ON flow_log_events
  BEGIN SELECT RAISE(ABORT,'Log toků je append-only'); END;
CREATE TRIGGER IF NOT EXISTS flow_log_events_delete BEFORE DELETE ON flow_log_events
  BEGIN SELECT RAISE(ABORT,'Log toků je append-only'); END;
"""

OWNER_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS flow_workflows_owner ON flow_workflows(project_id, kind, owner_ref)
  WHERE owner_ref IS NOT NULL;
"""
