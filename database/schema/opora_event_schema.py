"""OporaHub events outbox (docs/oporahub-events.md): one row per change, written in the change's transaction.

`id` is the monotonic cursor of the live process feed (AUTOINCREMENT never reuses an id, so a
pruned outbox never hands an old cursor to a new event). `opora_event_card_state` keeps the
last emitted stage and gate of each card so `stage.changed` / `gate.changed` fire only on change."""
TABLES = ("opora_events", "opora_event_card_state")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 kind TEXT NOT NULL, node_id TEXT, execution_id TEXT, step_id TEXT, pr_number INTEGER, stage TEXT, health TEXT,
 actor_kind TEXT NOT NULL, actor_name TEXT, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS opora_events_scope ON opora_events(project_id, workspace_id, id);
CREATE INDEX IF NOT EXISTS opora_events_at ON opora_events(at);
CREATE TABLE IF NOT EXISTS opora_event_card_state(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL, stage TEXT NOT NULL,
 health TEXT NOT NULL, reason TEXT NOT NULL, gate_status TEXT, gate_rule TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id, workspace_id, node_id));
"""
