Schéma a přístup k datům. Data leží ve složce každého projektu; centrální databáze už neexistuje.

| Soubor | Co obsahuje | Schéma |
|---|---|---|
| `.data/<root>/registry.sqlite` | jen to, co musí být vidět napříč projekty: `projects`, `project_sources`, `builtin_project_metadata`, `workspaces`, `jobs`, `archived_projects` | `database/schema/project_schema.py` → `REGISTRY_SCHEMA` |
| `.data/<root>/projects/<id>/project.sqlite` | vše o jednom projektu: `drafts`, `project_settings`, `node_text_revisions`, `node_spec_revisions`, `node_journal_revisions`, `drawing_revisions`, `graph_recoveries`, `desktop_v3_state`, `agent_workspace_revisions`, `desktop_v3_snapshots`, `workspace_documents`, `agent_bindings`, `agent_binding_scopes`, `agent_activity_entries`, `check_runs`, `opora_commits`, `node_sessions` | `PROJECT_SCHEMA` (vlastník tabulky v komentáři u každé tabulky) |
| `.data/<root>/projects/<id>/project.json` | identita projektu: ID, název, zdroj, nastavení | `backend/canvas/project_folder.py` |
| `.data/<root>/projects/<id>/processes/<prc-id>/` | procesy a odpovědi agentů (JSON soubory) | `shared/process.schema.json` |
| `.data/<root>/map-refresh/state.sqlite` | fronta obnovy map napříč projekty | `backend/project/maps/map_refresh.py` (zatím mimo složku projektu) |

`check_runs` je append-only záznam běhu kontrol u jednoho commitu (`backend/canvas/check_runs.py`): aplikace testy nespouští, jen zapisuje jejich výsledek, a oprava je nový řádek.

`opora_commits` je jen index OporaHubu (`backend/canvas/opora_hub.py`): pravda leží v souborech `projects/<id>/oporahub/<id>.json` a v append-only `oporahub/main.log`, ze kterých `rebuild_index` tabulku kdykoli postaví znovu.

Tabulky vytváří jen `CanvasService` (`db_for(project)` otevře `project.sqlite` a aplikuje `PROJECT_SCHEMA`); vlastnící moduly je čtou a píší. Stará `canvas.sqlite` se při prvním startu jednorázově rozdělí (`backend/canvas/migrate_to_project_folders.py`) a přejmenuje na `canvas.sqlite.migrated-<čas>`.

Podsložky `repositories/` a `seeds/` jsou sloty.
