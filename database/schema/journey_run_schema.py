"""Append-only doklady přehrání: cesty zákazníka (`docs/brana-cesty.md` §3, vlastník
`backend/project/architecture/journey_runs.py`) a záměru stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md`
§6, vlastník `backend/project/architecture/intent_runs.py`).

`at_utc` je čas běhu (`at`) převedený na UTC v pevném tvaru, aby řazení podle textu odpovídalo času; `seq`
rozhoduje shodu (později uložený vyhrává). Celý doklad leží v `record` (JSON), sloupce vedle jsou jen klíče
pro čtení. Řádek se nikdy nemění ani nemaže (triggery), oprava je nový doklad. Doklad záměru nese `stale`:
jeho `digest` v době zápisu neodpovídal aktivní verzi záměru.
"""
TABLES = ("journey_runs", "intent_runs")
SCHEMA = """
CREATE TABLE IF NOT EXISTS journey_runs(
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL, application_id TEXT NOT NULL, journey_id TEXT NOT NULL,
    at_utc TEXT NOT NULL, plan_digest TEXT NOT NULL, passed INTEGER NOT NULL,
    record TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS journey_runs_latest
    ON journey_runs(project_id, application_id, journey_id, at_utc, seq);
CREATE TRIGGER IF NOT EXISTS journey_runs_update BEFORE UPDATE ON journey_runs
BEGIN SELECT RAISE(ABORT, 'Immutable journey run'); END;
CREATE TRIGGER IF NOT EXISTS journey_runs_delete BEFORE DELETE ON journey_runs
BEGIN SELECT RAISE(ABORT, 'Immutable journey run'); END;
CREATE TABLE IF NOT EXISTS intent_runs(
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL, page_id TEXT NOT NULL, workflow_version_id TEXT NOT NULL,
    digest TEXT NOT NULL, stale INTEGER NOT NULL, record TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS intent_runs_page ON intent_runs(project_id, page_id, seq);
CREATE TRIGGER IF NOT EXISTS intent_runs_update BEFORE UPDATE ON intent_runs
BEGIN SELECT RAISE(ABORT, 'Immutable intent run'); END;
CREATE TRIGGER IF NOT EXISTS intent_runs_delete BEFORE DELETE ON intent_runs
BEGIN SELECT RAISE(ABORT, 'Immutable intent run'); END;
"""
