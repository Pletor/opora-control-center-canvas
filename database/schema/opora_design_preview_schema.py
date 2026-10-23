"""Design náhled karty (docs/design-nahled.md): screenshoty na hlavu PR, lidské potvrzení vzhledu, režim karty.

`opora_design_previews` drží doklad `evidence.preview` jednoho běhu pro jednu hlavu PR (`record` = režim,
otisk DESIGN.md, štítky a `fileId` screenshotů; bajty PNG leží v `drawing_files`).
`opora_design_preview_confirmations` drží „potvrzeno člověkem“ pro kartu a hlavu PR.
`opora_design_modes` drží režim design karty (`brand` / `explore`) s revizí; chybějící řádek = `brand`.
Vše je aditivní (`CREATE TABLE IF NOT EXISTS`), starý `project.sqlite` dostane tabulky při otevření."""
TABLES = ("opora_design_previews", "opora_design_preview_confirmations", "opora_design_modes")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_design_previews(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL, head_sha TEXT NOT NULL,
 node_id TEXT NOT NULL, pr_number INTEGER NOT NULL, record TEXT NOT NULL, by TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id,head_sha));
CREATE INDEX IF NOT EXISTS opora_design_previews_node ON opora_design_previews(project_id,workspace_id,node_id);
CREATE TABLE IF NOT EXISTS opora_design_preview_confirmations(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL, head_sha TEXT NOT NULL,
 by TEXT NOT NULL, confirmed_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,node_id,head_sha));
CREATE TABLE IF NOT EXISTS opora_design_modes(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL, mode TEXT NOT NULL,
 revision INTEGER NOT NULL, by TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,node_id));
"""
