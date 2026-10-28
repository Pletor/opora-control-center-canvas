"""Nálezy strážců (`docs/strazci.md` §3); vlastník `backend/canvas/strazci/findings.py`.

Jeden řádek = jeden nález se stabilním `key`. Otevřený nález má `resolved_at` NULL; když ho strážce přestane
hlásit, dostane čas vyřešení, a když se vrátí, řádek se znovu otevře. `payload` (JSON) nese pole nálezu mimo
sloupce (`journeyId`, `executionId`, `data`, `workspaceId`). Vyřešené nálezy starší 14 dní se mažou.
"""
TABLES = ("guard_findings",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS guard_findings(
    key TEXT PRIMARY KEY, project_id TEXT NOT NULL, guard TEXT NOT NULL, rule TEXT NOT NULL,
    severity TEXT NOT NULL, message TEXT NOT NULL, node_id TEXT, payload TEXT NOT NULL,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, resolved_at TEXT);
CREATE INDEX IF NOT EXISTS guard_findings_open ON guard_findings(project_id, guard, resolved_at);
CREATE INDEX IF NOT EXISTS guard_findings_node ON guard_findings(project_id, node_id, resolved_at);
"""
