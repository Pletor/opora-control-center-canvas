"""Vstupní brána požadavků (docs/navrhy/2026-10-30-vstupni-brana.md §5); vlastník `backend/brain_opora/determinism/intake.py`.

`intake_entries` = doslovný a neměnný otisk jedné věty (panel srdce, lístek `change`/`ask`, fragment Schránky)
se stanoviskem brány. `intake_entries_fts` je FTS5 nad `text` s vlastní kopií textu a `entry_id` (ne vnější obsah:
rowid tabulky s textovým klíčem se po VACUUM smí přečíslovat). Řádek do ní píše repozitář spolu se vstupem;
vstup se nikdy nepřepisuje ani nemaže, takže se obě tabulky nerozejdou.
`intake_requirements` píše srdce přes `opora_heart.py intake --requirement` a `intake_milestones` návrh srdce
(`opora_heart.py milestone`, stav `proposed`) a rozhodnutí člověka (`POST /api/intake/milestone`);
docs/navrhy/2026-10-30-metriky-a-spoustece.md §5. Starší databáze s CHECK bez `proposed` přestaví jednou
`project_schema.ensure_milestone_proposed`.
`heart_triggers` = „už jsem budil“: klíč spouštěče (`trigger:milestone:<id>:done`) se zapíše jednou, srdce se tím
na stejný stav nebudí podruhé (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4).
`intake_briefs` = spis výslechu jednoho požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §6): situace, rešerše,
syntéza a otázky jako JSON. Nová tabulka, aditivní; píše ji `backend/brain_opora/determinism/brief.py`.
"""
TABLES = ("intake_entries", "intake_requirements", "intake_milestones", "heart_triggers", "intake_briefs")
BRIEFS_TABLE = """
CREATE TABLE IF NOT EXISTS intake_briefs(
    requirement_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','research','grilling','clear')),
    situation TEXT NOT NULL DEFAULT '{}', research TEXT NOT NULL DEFAULT '[]', synthesis TEXT,
    questions TEXT NOT NULL DEFAULT '[]', rounds INTEGER NOT NULL DEFAULT 0, cost_usd REAL,
    updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS intake_briefs_workspace ON intake_briefs(workspace_id, status);
"""
MILESTONES_TABLE = """
CREATE TABLE IF NOT EXISTS intake_milestones(
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, area_id TEXT NOT NULL, title TEXT NOT NULL,
    criteria TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK(status IN ('proposed','active','done','superseded')),
    created_at TEXT NOT NULL);
"""
MILESTONES_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS intake_milestones_one_active
    ON intake_milestones(workspace_id, area_id) WHERE status='active';
"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS intake_entries(
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('heart_message','gate_change','gate_ask','brief_fragment')),
    source_ref TEXT, text TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
    verdict TEXT NOT NULL, layer TEXT NOT NULL, area_id TEXT, milestone_id TEXT, requirement_id TEXT,
    confidence REAL, reason TEXT, cost_usd REAL, jev_calls INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS intake_entries_fingerprint ON intake_entries(workspace_id, fingerprint, created_at);
CREATE INDEX IF NOT EXISTS intake_entries_recent ON intake_entries(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS intake_entries_source ON intake_entries(source, source_ref);
CREATE VIRTUAL TABLE IF NOT EXISTS intake_entries_fts USING fts5(
    text, entry_id UNINDEXED, workspace_id UNINDEXED, tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS intake_requirements(
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, area_id TEXT, milestone_id TEXT, title TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open','deferred','done','superseded')),
    open_condition TEXT, supersedes TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS intake_requirements_area ON intake_requirements(workspace_id, area_id, status);
CREATE TABLE IF NOT EXISTS heart_triggers(
    key TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, fired_at TEXT NOT NULL);
""" + MILESTONES_TABLE + MILESTONES_INDEX + BRIEFS_TABLE
