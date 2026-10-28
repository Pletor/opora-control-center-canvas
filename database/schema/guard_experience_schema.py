"""Zkušenost strážců pro OpenViking (`docs/strazci.md` §4, strážce `zkusenost`); vlastník
`backend/canvas/strazci/guard_zkusenost.py`.

`guard_experience` je outbox ve vzoru `harness_memory_deliveries`: jeden řádek = jeden deterministický záznam
zkušenosti (`payload`, JSON) k jednomu zdroji (`source` `event` = `opora_events.id` uzavření karty nebo merge PR,
`journey` = `journey_runs.seq` dokladu cesty). Doručení bere řádek nárokem (`lease_owner`, `lease_until`), neúspěch
vrací `retry` s rostoucím odkladem, chybějící role `waiting-role`. Řádek se po zápisu do OpenViking nemaže.
`guard_experience_cursor` drží, kam strážce v každém zdroji dočetl (přežije restart).
"""
TABLES = ("guard_experience", "guard_experience_cursor")
SCHEMA = """
CREATE TABLE IF NOT EXISTS guard_experience(
    project_id TEXT NOT NULL, source TEXT NOT NULL, source_id INTEGER NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, payload TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending','retry','waiting-role','working','submitted')),
    attempts INTEGER NOT NULL CHECK(attempts>=0), next_attempt REAL NOT NULL, lease_owner TEXT NOT NULL,
    lease_until REAL NOT NULL, role_id TEXT NOT NULL, uri TEXT NOT NULL, error TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, source, source_id));
CREATE INDEX IF NOT EXISTS guard_experience_pending ON guard_experience(project_id, state, next_attempt);
CREATE TABLE IF NOT EXISTS guard_experience_cursor(
    project_id TEXT NOT NULL, source TEXT NOT NULL, cursor INTEGER NOT NULL, PRIMARY KEY(project_id, source));
"""
