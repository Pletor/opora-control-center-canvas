Schéma a přístup k datům. Data leží ve složce každého projektu; centrální databáze už neexistuje.

| Soubor | Co obsahuje | Schéma |
|---|---|---|
| `.data/<root>/registry.sqlite` | jen to, co musí být vidět napříč projekty: `projects`, `project_sources`, `builtin_project_metadata`, `workspaces`, `jobs`, `archived_projects`, engine toků `flow_*` (`database/schema/flow_schema.py`, vlastník `backend/flow/`) | `database/schema/project_schema.py` → `REGISTRY_SCHEMA` |
| `.data/<root>/projects/<id>/project.sqlite` | vše o jednom projektu: `drafts`, `project_settings`, `project_profile`, `node_text_revisions`, `node_spec_revisions`, `node_journal_revisions`, `drawing_revisions`, `drawing_files`, `graph_recoveries`, `removal_restores`, `desktop_v3_state`, `agent_workspace_revisions`, `desktop_v3_snapshots`, `workspace_documents`, `check_runs`, `opora_commits`, `journey_runs`, `studio_models`, `guard_findings` | `PROJECT_SCHEMA` (vlastník tabulky v komentáři u každé tabulky) |
| `.data/<root>/projects/<id>/project.json` | identita projektu: ID, název, zdroj, nastavení | `backend/canvas/project_folder.py` |
| `.data/<root>/map-refresh/state.sqlite` | fronta obnovy map napříč projekty | `backend/project/maps/map_refresh.py` (zatím mimo složku projektu) |

`check_runs` je append-only záznam běhu kontrol u jednoho commitu (`backend/canvas/check_runs.py`): aplikace testy nespouští, jen zapisuje jejich výsledek, a oprava je nový řádek.

`journey_runs` je append-only doklad přehrání cesty zákazníka (`backend/project/architecture/journey_runs.py`, schéma `database/schema/journey_run_schema.py`, přístup `database/repositories/journey_runs.py`, kontrakt `docs/brana-cesty.md` §3): Opora cestu nepřehrává, doklad jen ověří a uloží; triggery brání změně i smazání.

`studio_models` drží technický model domény Studia (`backend/project/studio/studio_model.py`, schéma `database/schema/studio_model_schema.py`, přístup `database/repositories/studio_models.py`, kontrakt `docs/studio.md` §4): jedna aktuální verze `opora.studio-model/1` na doménu s optimistickou revizí, bez historie; graf projektu se kvůli ní nikdy nemění.

`guard_findings` drží nálezy strážců (`backend/canvas/strazci/findings.py`, schéma `database/schema/guard_findings_schema.py`, přístup `database/repositories/guard_findings.py`, kontrakt `docs/strazci.md` §3): stabilní `key`, otevřený nález má `resolved_at` NULL, vyřešené starší 14 dní se mažou.

`opora_commits` je jen index OporaHubu (`backend/canvas/opora_hub.py`): pravda leží v souborech `projects/<id>/oporahub/<id>.json` a v append-only `oporahub/main.log`, ze kterých `rebuild_index` tabulku kdykoli postaví znovu.

Tabulky vytváří jen `CanvasService` (`db_for(project)` otevře `project.sqlite` a aplikuje `PROJECT_SCHEMA`); vlastnící moduly je čtou a píší. Stará `canvas.sqlite` se při prvním startu jednorázově rozdělí (`backend/canvas/migrate_to_project_folders.py`) a přejmenuje na `canvas.sqlite.migrated-<čas>`.

Mrtvé tabulky `node_sessions`, `agent_bindings`, `agent_binding_scopes` a `agent_activity_entries` (po odstraněném vázání agentů na uzly) maže při otevření projektu `database/schema/dead_tables.py` (audit sirotků B8): jen prázdné a jen v projektu, který není zapsaný do SQL kontextu (`opora_context_coverage`), protože každé DDL posune `PRAGMA schema_version`. Před nasazením zálohuj `projects/*/project.sqlite`.

Podsložky `repositories/` a `seeds/` jsou sloty.
