Schéma, migrace a přístup k datům. Dnes je zde jen dokumentace: každá tabulka vzniká CREATE TABLE IF NOT EXISTS v modulu, který ji vlastní.

| Databáze | Tabulka | Vlastnící modul |
|---|---|---|
| canvas.sqlite | projects, workspaces, drafts, jobs | backend/canvas/canvas_service.py |
| canvas.sqlite | project_sources, project_settings, builtin_project_metadata | backend/project_setup/project_hub.py |
| canvas.sqlite | workspace_documents | backend/project/workspace/workspace_documents.py |
| canvas.sqlite | node_text_revisions | backend/editor/node/node_text.py |
| canvas.sqlite | node_spec_revisions | backend/editor/node/node_specs.py |
| canvas.sqlite | node_journal_revisions | backend/editor/node/node_journal.py |
| canvas.sqlite | drawing_revisions | backend/editor/node/drawings.py |
| canvas.sqlite | graph_recoveries, archived_projects | backend/editor/node/removals.py |
| canvas.sqlite | desktop_v3_* (stav) | backend/editor/agent_memory/desktop_v3_state.py |
| canvas.sqlite | desktop_v3_* (snímky packetů) | backend/editor/agent_packet/desktop_v3_packets.py |
| canvas.sqlite | node_sessions | backend/live_run/node_sessions.py |
| canvas.sqlite | agent_activity_entries | backend/live_run/agent_activity.py |
| canvas.sqlite | agent_bindings, agent_binding_scopes | backend/live_run/agent_bindings.py |
| state.sqlite | config, projects, runs | backend/project/maps/map_refresh.py |

Podsložky schema/, repositories/, seeds/ jsou sloty: kód sem přijde vyjmutím z uvedených modulů.
