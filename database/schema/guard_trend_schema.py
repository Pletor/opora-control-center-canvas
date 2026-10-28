"""Trend strážců (`docs/strazci.md` §4, strážce `trend`); vlastník `backend/canvas/strazci/guard_trend.py`.

Jeden řádek = jedno souhrnné číslo projektu v jednom vzorku (`at` ISO v UTC, stejný tvar jako `at` událostí,
takže řazení podle textu odpovídá času). Vzorek bere strážce `trend` každých 900 s; řádky starší 90 dní se při
zápisu mažou. Nic jiného tabulku nepíše.
"""
TABLES = ("guard_trend",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS guard_trend(
    project_id TEXT NOT NULL, at TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL,
    PRIMARY KEY(project_id, metric, at));
CREATE INDEX IF NOT EXISTS guard_trend_at ON guard_trend(project_id, at);
"""
