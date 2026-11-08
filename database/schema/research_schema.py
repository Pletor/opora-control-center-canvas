"""Additive, immutable research graph revisions scoped to a workspace."""
TABLES = ("research_card_revisions", "research_edge_revisions", "research_batches")
SCHEMA = ""
for table in TABLES[:2]:
    SCHEMA += f"""
CREATE TABLE IF NOT EXISTS {table} (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision > 0), payload TEXT NOT NULL,
 PRIMARY KEY(project_id, workspace_id, id, revision)
);
"""
SCHEMA += """
CREATE TABLE IF NOT EXISTS research_batches (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, key TEXT NOT NULL,
 digest TEXT NOT NULL, response TEXT NOT NULL,
 PRIMARY KEY(project_id, workspace_id, key)
);
"""
