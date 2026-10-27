# Plán struktury `backend/` a `database/` (provedeno; doplněno o vyjmutí routerů a testy vedle modulů)

Cíl: backend má na první úrovni stejný příběh jako frontend:
**project_setup → project | editor**, pod nimi společný základ plátna a platforma.
Každé prostředí má připravené místo pro logiku, která bude přibývat: paměť agentů, předávání
struktury, textů a kreseb agentovi jako jednotlivý uzel (vykonat úkol) nebo celý sektor (zpracovat).
Nad prostředími se postaví nové robustní API (`api/` rozdělené stejně podle prostředí) a nad API
MCP server (`mcp/`), kterým agenti aplikaci ovládají.
Chování se nemění; mění se jen cesty, názvy balíčků, název jednoho souboru a import řádky.

## 0. Co inventář zjistil (stav na disku, 125 souborů)

- Importy jsou všude absolutní `from backend.x.y import …`. Kořen: `pyproject.toml` `pythonpath=["."]`, `testpaths=["backend","tools"]`. Aplikaci spouští `tools/serve-preview.py` přes `backend.app.create_app`.
- Testy leží v `tests/` každého balíčku; osm jich testuje jiný balíček, než kde leží.
- `database/` obsahuje jen 4 README. Všech 20 SQLite tabulek vzniká `CREATE TABLE IF NOT EXISTS` uvnitř 13 modulů.
- Názvy bez obsahu: `domain/service.py` (CanvasService), `agents/runs/` (jen export úkolu), `agents/packets/` (paměť + podklady dohromady).
- Routery mimo `api/`: `workspace_sources.py`, `map_refresh.py`, 25 inline rout v `app/factory.py`. Vyjmutí = rozdělení souboru = změna obsahu → dluh v §5.
- Baseline testů: 282 passed, 2 failed (graphify, externí nástroj), 6 skipped.

## 1. Pravidla

| Šuplík balíčku | Co obsahuje |
|---|---|
| kořen balíčku | moduly s logikou (`.py`) + `__init__.py` |
| `test_<modul>.py` | test leží hned vedle modulu, který testuje (v seznamu souborů pod ním); žádné složky tests/ |
| `README.md` | první věta: co balíček dělá a pro které prostředí frontendu pracuje |

- Balíčky snake_case; název souboru říká, co dělá. Žádné `utils`, `misc`, `common`, `helpers`, verze.
- Routery pouze v `api/<prostředí>/`; moduly prostředí žádný APIRouter nevytvářejí.
- Směr závislostí: `mcp/` → `api/` → prostředí (`project_setup`, `project`, `editor`) → `canvas/`, `integrations/`. Nižší vrstva nikdy neimportuje vyšší. (Dnes porušeno jednou: `graph.py` → `workspace_sources`, viz §5.)
- Žádná změna obsahu modulů, žádné rozdělování souborů, žádné mazání. Přesun výhradně `git mv`.

## 2. Cílový strom

```
backend/
├── README.md · STRUCTURE-PLAN.md · __init__.py · paths.py
├── app/                    spuštění aplikace: create_app, middleware, mount dist/
│   ├── factory.py
│   └── tests/  test_api · test_backend_review_guards · test_v3_acceptance
├── api/                    ROBUSTNÍ API: tenké routery rozdělené podle prostředí, nad nimi MCP
│   ├── project/            graphify_routes  + tests/ (test_graphify_routes)
│   ├── editor/             desktop_v3_routes
│   └── project_setup/      README (slot): rozhraní pro připojení a založení projektu (dnes inline v app/factory.py)
├── mcp/                    MCP SERVER nad api/: get_tree, get_node, claim_task… README (slot, dříve agents/control)
│
├── canvas/                 ZÁKLAD PLÁTNA společný všem prostředím
│   ├── canvas_service.py   (dříve domain/service.py) DB canvas.sqlite, git sync, view/save grafu
│   ├── graph.py            validace a digest grafu, zdrojové reference
│   └── tests/  test_canvas · test_responsiveness · test_sync · test_snapshot · test_map_links · test_graph_source_ref · test_paths
│
├── project_setup/          KROK 1: přiřazení repozitářů a složek, vytvoření projektu
│   ├── project_hub.py
│   └── tests/  test_project_hub · test_project_hub_concurrency
│
├── project/                PROSTŘEDÍ PROJEKT: pohled na main
│   ├── workspace/          strom zdrojů, otevírání souborů, dokumentace k cestám
│   │   ├── workspace_sources.py · workspace_documents.py
│   │   └── tests/  test_workspace_sources (+ sdílené helpery attach/ORIGIN) · test_workspace_documents · test_workspace_source_safety · test_working_source_tree · test_source_creation_user_contract · test_empty_workspace_source · test_workspace_goal
│   └── maps/               Graphify, fronta obnovy map
│       ├── graphify_runtime · graphify_worker · map_artifacts · map_refresh · map_refresh_pipeline · map_refresh_snapshot
│       └── tests/  test_map_refresh
│
├── editor/                 PROSTŘEDÍ EDITOR: obsah uzlů a vše, co dostává agent
│   ├── node/               obsah jednoho uzlu
│   │   ├── node_text · node_specs · node_journal · node_links · drawings · wireframe_context · removals
│   │   └── tests/  test_node_text · test_node_specs · test_node_journal · test_block_links · test_drawings · test_wireframe_context · test_removals · test_removal_history
│   ├── sector/             README (slot): zpracování celého sektoru
│   ├── agent_memory/       paměť projektu pro agenty: pravidla, rozhodnutí, fáze uzlu
│   │   ├── desktop_v3_state.py
│   │   └── tests/  test_desktop_v3_state
│   ├── agent_packet/       podklady pro agenta: složení uzlu (text, zadání, kresby, dokumentace) do packetu
│   │   ├── desktop_v3_packets.py · redact.py
│   │   └── tests/  test_desktop_v3_packets
│   ├── agent_handoff/      předání úkolu externímu agentovi (Markdown export snímku)
│   │   ├── external_agent_tasks.py
│   │   └── tests/  __init__ (slot)
│   └── task_execution/     README (slot): vykonání úkolu z uzlu podle ID – najít zadání, podrobnosti, dotáhnout do konce; zpracování sektoru
│
├── integrations/           PLATFORMA: gitio · windows_job · build_identity  + tests/test_build_identity
├── claude_code/            README (slot): commands, skills řízené z aplikace
└── library/                README (slot): předlohy, checklisty, zpětná vazba

database/                   dnes dokumentace: kde která tabulka žije
├── README.md               mapa 20 tabulek → vlastnící modul (§3.4)
└── schema/ · repositories/ · seeds/   README sloty
```

Zanikají balíčky `domain/`, `agents/`, `maps/` – všechny soubory jsou přesunuty, nic se nemaže.

## 3. Tabulka přesunů

### 3.1 canvas/, project_setup/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| domain/service.py | canvas/canvas_service.py | RN; název říká obsah |
| domain/graph/graph.py | canvas/graph.py | základ grafu, používají ho všechna prostředí |
| domain/README.md | canvas/README.md | text přepsat |
| domain/graph/README.md, __init__.py | – → canvas/__init__.py vzniká z domain/__init__.py; graph/__init__.py se přesune jako canvas/tests/__init__.py | žádné mazání |
| app/tests/test_canvas.py, test_responsiveness.py | canvas/tests/ | testují CanvasService |
| integrations/tests/test_sync.py | canvas/tests/test_sync.py | CanvasService.sync |
| domain/project/tests/test_snapshot.py | canvas/tests/test_snapshot.py | CanvasService (SHA main) |
| domain/node/tests/test_map_links.py, test_graph_source_ref.py | canvas/tests/ | testují graph.py |
| app/tests/test_paths.py | canvas/tests/test_paths.py | paths.py je základ cest |
| domain/project/project_hub.py, README.md, __init__.py | project_setup/ | krok 1 |
| domain/project/tests/test_project_hub.py, test_project_hub_concurrency.py, __init__.py | project_setup/tests/ | |

### 3.2 project/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| integrations/workspace_sources.py, workspace_documents.py | project/workspace/ | strom a dokumentace projektu, ne integrace |
| integrations/tests/test_workspace_sources.py, test_workspace_documents.py, test_workspace_source_safety.py, test_working_source_tree.py, test_source_creation_user_contract.py | project/workspace/tests/ | |
| domain/project/tests/test_empty_workspace_source.py, test_workspace_goal.py | project/workspace/tests/ | testují spravovaný strom a kořenový dokument |
| maps/* (7 modulů, README, __init__, tests/) | project/maps/ | mapy jsou pohled na main |
| – | project/__init__.py, README.md; project/workspace/__init__.py, README.md; project/workspace/tests/__init__.py | nové |

### 3.3 editor/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| domain/node/{node_text,node_specs,node_journal,node_links,drawings,removals}.py, README.md, __init__.py | editor/node/ | obsah uzlu |
| domain/project/wireframe_context.py | editor/node/wireframe_context.py | projekce kresby patří k drawings |
| domain/node/tests/{test_node_text,test_node_specs,test_node_journal,test_block_links,test_drawings,test_removals,test_removal_history}.py, __init__.py | editor/node/tests/ | |
| domain/project/tests/test_wireframe_context.py | editor/node/tests/ | |
| domain/sector/README.md | editor/sector/README.md | slot: zpracování sektoru |
| agents/packets/desktop_v3_state.py | editor/agent_memory/desktop_v3_state.py | paměť projektu a fáze uzlu |
| agents/packets/tests/test_desktop_v3_state.py | editor/agent_memory/tests/ | |
| agents/packets/desktop_v3_packets.py, redact.py, README.md, __init__.py | editor/agent_packet/ | podklady pro agenta |
| agents/packets/tests/test_desktop_v3_packets.py, __init__.py | editor/agent_packet/tests/ | |
| agents/runs/external_agent_tasks.py, README.md, __init__.py | editor/agent_handoff/ | předání úkolu ven |
| agents/runs/tests/__init__.py | editor/agent_handoff/tests/__init__.py | slot |
| agents/control/README.md | mcp/README.md | MCP server nad API, vlastní balíček na první úrovni |
| api/graphify_routes.py | api/project/ | rozhraní prostředí Projekt |
| api/tests/test_graphify_routes.py, __init__.py | api/project/tests/ | |
| api/desktop_v3_routes.py | api/editor/desktop_v3_routes.py | rozhraní Editoru |
| api/README.md, __init__.py | zůstávají; + api/project/__init__.py, api/editor/__init__.py, api/project_setup/README.md | nové |
| agents/README.md, agents/__init__.py | editor/README.md, editor/__init__.py | text přepsat |
| – | editor/agent_memory/__init__.py + tests/__init__.py + README; editor/task_execution/README.md | nové |

### 3.4 database/ – žádný přesun, jen dokumentace
`database/README.md` dostane tabulku „tabulka → modul, který ji vytváří“: canvas.sqlite: projects, workspaces, drafts, jobs → canvas/canvas_service; drawing_revisions → editor/node/drawings; node_journal_revisions → editor/node/node_journal; node_spec_revisions → editor/node/node_specs; node_text_revisions → editor/node/node_text; graph_recoveries, archived_projects → editor/node/removals; project_sources, project_settings, builtin_project_metadata → project_setup/project_hub; workspace_documents → project/workspace/workspace_documents; desktop_v3_* → editor/agent_memory, editor/agent_packet; state.sqlite: config, projects, runs → project/maps/map_refresh.

## 4. Co se přepíše
| Starý modul | Nový modul |
|---|---|
| backend.domain.service | backend.canvas.canvas_service |
| backend.domain.graph.graph | backend.canvas.graph |
| backend.domain.project.project_hub | backend.project_setup.project_hub |
| backend.domain.project.wireframe_context | backend.editor.node.wireframe_context |
| backend.domain.node.* (ostatní) | backend.editor.node.* |
| backend.integrations.workspace_sources, workspace_documents | backend.project.workspace.* |
| backend.integrations.tests.test_workspace_sources | backend.project.workspace.tests.test_workspace_sources |
| backend.maps.* | backend.project.maps.* |
| backend.agents.packets.desktop_v3_state | backend.editor.agent_memory.desktop_v3_state |
| backend.agents.packets.desktop_v3_packets, redact | backend.editor.agent_packet.* |
| backend.agents.runs.external_agent_tasks | backend.editor.agent_handoff.external_agent_tasks |
| backend.api.graphify_routes | backend.api.project.* |
| backend.api.desktop_v3_routes | backend.api.editor.desktop_v3_routes |
| řetězec "backend.domain.service.git" (4 testy) | "backend.canvas.canvas_service.git" |

Beze změny: `pyproject.toml`, `tools/serve-preview.py` (`backend.app`), `tools/tests` (`backend.paths`).
Dokumentace: `.claude/skills/opora-control-center/references/{source-map,api,graphify}.md`, `docs/pravidla-struktury.md`, README každého balíčku.

## 5. Evidovaný dluh (vyžaduje změnu obsahu souborů, mimo rozsah)
1. HOTOVO: routery vyjmuty do `api/project/workspace_routes.py`, `api/project/map_refresh_routes.py`; 25 inline rout z `app/factory.py` rozděleno do `api/app_routes.py`, `api/project_setup/project_routes.py`, `api/project/project_workspace_routes.py`, `api/editor/canvas_routes.py`, `api/editor/node_routes.py`. `mcp/` bude volat jen `api/`.
2. `canvas/graph.py` importuje `project/workspace/workspace_sources.relative_path` (základ závisí na prostředí).
3. `integrations/build_identity.py` hashuje `backend/*.py` a `src/*`; po restrukturalizaci hashuje jen `paths.py`.
4. `desktop_v3_state.py` drží paměť projektu i fáze uzlu v jednom souboru; při růstu rozdělit na `agent_memory` a `workflow`.
5. `database/repositories` naplnit vyjmutím tabulek z modulů v §3.4.
6. `editor/task_execution` a `editor/sector` jsou sloty pro budoucí vykonávání úkolů; README popíše vstupy (ID uzlu → zadání, text, kresby, dokumentace, paměť) a výstup (dotažený úkol).

## 6. Ověření po fázi 2
1. `uv run pytest -q` – cíl: 282 passed, stejné 2 graphify selhání, 6 skipped
2. `uv run ruff check backend tools` – žádné nové nálezy
3. `git status --short` – jen R, M, A; žádné D z této migrace
4. grep na staré moduly (`backend.domain`, `backend.agents`, `backend.maps`, `backend.integrations.workspace`, `backend.api.[a-z_]+_routes`) v backend, tools, .claude, docs → 0 nálezů

## 7. Doplněk: testy vedle modulů
Všech 44 testů přejmenováno na `test_<modul>.py` a přesunuto ze složek `tests/` přímo vedle testovaného modulu (např. `node_text.py` + `test_node_text.py`). Více testů k jednomu modulu: `test_<modul>_<téma>.py` (např. `test_canvas_service_sync.py`). Sdílené helpery `attach()`/`ORIGIN` žijí v `project/workspace/test_workspace_sources.py`. Ruff vylučuje `**/test_*.py`. VS Code zanoří test pod modul přes `explorer.fileNesting` v `.vscode/settings.json` (vzor `test_${capture}.py, test_${capture}_*.py`), takže po rozkliknutí souboru je test hned pod ním.
