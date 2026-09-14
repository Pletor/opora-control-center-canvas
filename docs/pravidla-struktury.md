# Pravidla struktury projektu

Tento dokument je autorita pro umístění nového souboru. Při pochybnosti se řídí tímto pořadím otázek.

```
opora-canvas/
  frontend/             # cesta uživatele: nastavení → Projekt | Editor | Live Run
    app/                # main.tsx, App.tsx, theme, barrel panelů (skládání prostředí)
    design-tokens/      # theme-tokens.css: barvy, témata, hustota
    layout/             # kostra obrazovky společná všem prostředím
      top-bar/
      environment-switch/ # Projekt | Editor | Live Run (Alt+1..3)
      mode-rail/        # módy plátna uvnitř Editoru
      account-corner/   # levý dolní roh: tlačítko Opora a popup menu
      shell/            # styly pracovní plochy
    project-setup/      # KROK 1: přiřazení repozitářů a složek, vytvoření projektu
    project/            # PROSTŘEDÍ PROJEKT: pohled na main
      shell/            # levý strom + navigace map (ProjectLayout)
      source-tree/      # strom složek a souborů (SourceExplorer)
      maps/             # Archify, Graphify, obnova map
      workspace/        # složení plochy, dokumentace k cestám
    editor/             # PROSTŘEDÍ EDITOR: řízení vývoje
      canvas/           # board, drawing (Excalidraw), wireframes, node-card, sector-card
      node-detail/      # NodePanel: content, assignment, process (návrh → proces → hotovo → oprava), journal, links
      sector-detail/    # stejná šablona jako node-detail
      workflow/         # fáze, kritéria, kroky uzlu → základ pipeline
      component-library/ # LEVÁ STRANA: knihovna komponent, metod, funkcí (palette/)
      llm-control/      # PRAVÁ STRANA: Claude Code hooky, skills, commandy, agenti
        project-memory/ # pravidla, rozhodnutí, nastavení
        editor-context/ # reference a „úkol pro agenta“
        agent-packet/   # podklady pro agenta: náhled, snímek, export
    live-run/           # PROSTŘEDÍ LIVE RUN: jak agenti pracují
      run-monitor/      # běhy agentů a jejich důkazy
      node-sessions/    # živé session na uzlu
      node-activity/    # aktivita agentů na uzlu (záložka Práce)
      processes/        # přehled procesů projektu: oprava, proces, návrh, hotovo
    shared/             # bez závislosti na prostředích
      api/              # slot: jeden klient nad backend API
      types/  hooks/  contexts/
      desktop-state/    # stav panelů (paměť, workflow, podklady)
      selection/        # vybraný zdroj, reference, poznámka
      surface-settings/ # mřížka, přichytávání, mód
    settings/           # nastavení aplikace z levého dolního rohu: Obecné, Plátno, Projekt, Skills (Claude Code), Connectors
    ui-kit/             # prvky bez domény: removal-dialog, workspace-boundary, panel-frame
    (uvnitř každé feature složky: components/ = .tsx · logic/ = .ts · styles/ = .css · README)

  backend/              # stejný příběh jako frontend; mcp → api → prostředí → canvas, integrations
    app/                # create_app, middleware, mount dist/, skládání routerů z api/
    api/                # ROBUSTNÍ API: tenké routery podle prostředí; app_routes = zdraví, identita, bootstrap
      project_setup/    # project_routes: nastavení, lokální/prázdný projekt, connect
      project/          # project_workspace_routes, workspace_routes, archify_routes, graphify_routes, map_refresh_routes
      editor/           # canvas_routes, node_routes, desktop_v3_routes, claude_code_routes, process_routes
      live_run/         # agent_routes, node_session_routes
    mcp/                # MCP server nad api/ (slot)
    canvas/             # základ plátna: canvas_service (registr + db_for(projekt), git sync, graf), graph, project_folder (projects/<id>/), project_registry, migrate_to_project_folders
    project_setup/      # KROK 1: project_hub (připojení repozitáře, založení projektu)
    project/            # PROSTŘEDÍ PROJEKT
      workspace/        # strom zdrojů, otevírání souborů, dokumentace k cestám
      worktrees/        # worktree_manager: worktree z čistého main, fork, run_check, úklid
      maps/             # graphify, archify, map_refresh, artefakty, snapshoty
    editor/             # PROSTŘEDÍ EDITOR: obsah uzlů a vše, co dostává agent
      node/             # node_text, node_specs, node_journal, node_links, drawings, wireframe_context, removals
      sector/           # slot: zpracování celého sektoru
      agent_memory/     # desktop_v3_state: pravidla, rozhodnutí, fáze uzlu
      agent_packet/     # desktop_v3_packets, redact: podklady pro agenta
      agent_handoff/    # external_agent_tasks: předání úkolu externímu agentovi
      process/          # process_store, process_lifecycle (návrh → proces → hotovo → oprava), process_reports (odpovědi agentů)
      task_execution/   # slot: vykonání úkolu z uzlu podle ID
    live_run/           # PROSTŘEDÍ LIVE RUN: agent_sources, agent_catalog, agent_bindings, agent_activity, agent_telemetry, node_sessions
    integrations/       # platforma: gitio, windows_job, build_identity
    claude_code/        # skills_catalog (SKILL.md z projektu, uživatele, pluginů), skill_preferences (vypnuté skills); hooky a commands přibudou
    library/            # slot: načítání a verze předloh
    (každý balíček má README; test leží vedle modulu jako test_<modul>.py)

  database/             # kde data žijí: registry.sqlite + projects/<id>/project.sqlite (database/README.md)
    schema/             # project_schema.py: REGISTRY_SCHEMA a PROJECT_SCHEMA po tabulkách s vlastníkem
    repositories/       # slot: přístup k datům vyčleněný z modulů
    seeds/              # slot: výchozí obsah knihovny předloh

  library/              # DATA knihovny předloh, verzované v gitu
    components/<name>/  # blueprint.md + checklist.yaml + šablona kódu
    functions/
    methods/
    lessons/            # zaznamenané chyby → návrhy aktualizace předloh

  .claude/              # co čte Claude Code: hooks/, commands/, skills/ (opora-control-center, prompt-master)
  shared/               # JSON schémata kontraktů FE ↔ BE ↔ agenti
  docs/                 # PRODUCT-CONTRACT, pravidla struktury, ADR, tento spec
  tools/                # build a dev skripty: copy-drawing-assets, serve-preview
  vendor/archify/
```

Pravidla umístění nového souboru:

1. Vidí to uživatel? → `frontend/`. Kde v cestě uživatele to je? → `project-setup/`, `project/`, `editor/` nebo `live-run/`. Je to obecné (bez domény)? → `ui-kit/`. Sdílený stav bez závislosti na prostředí? → `shared/`. Uvnitř složky: .tsx do `components/`, .ts do `logic/`, .css do `styles/`.
2. Je to logika, proces, integrace? → `backend/`. Kde v cestě uživatele to je? → `project_setup/`, `project/`, `editor/` nebo `live_run/`. Router jen do `api/<prostředí>/`. Základ plátna → `canvas/`, platforma → `integrations/`.
3. Je to schéma nebo přístup k datům? → `database/`.
4. Je to předloha, checklist nebo poučení? → `library/`.
5. Test leží hned vedle toho, co testuje, jako `test_<modul>.py` (backend) nebo `<Name>.test.tsx` (frontend); žádné složky tests/. Css leží ve `styles/` vedle komponenty. Název souboru říká, co dělá a k čemu patří.

## Skutečný stav

```
backend
backend/api
backend/api/editor
backend/api/live_run
backend/api/project
backend/api/project_setup
backend/app
backend/canvas
backend/claude_code
backend/editor
backend/editor/agent_handoff
backend/editor/agent_memory
backend/editor/agent_packet
backend/editor/node
backend/editor/sector
backend/editor/task_execution
backend/integrations
backend/library
backend/live_run
backend/mcp
backend/project
backend/project/maps
backend/project/workspace
backend/project_setup
database
database/repositories
database/schema
database/seeds
frontend
frontend/app
frontend/app/components
frontend/app/logic
frontend/app/styles
frontend/design-tokens
frontend/design-tokens/styles
frontend/editor
frontend/editor/canvas
frontend/editor/canvas/board
frontend/editor/canvas/board/components
frontend/editor/canvas/drawing
frontend/editor/canvas/drawing/components
frontend/editor/canvas/drawing/logic
frontend/editor/canvas/drawing/styles
frontend/editor/canvas/node-card
frontend/editor/canvas/sector-card
frontend/editor/canvas/settings
frontend/editor/canvas/settings/components
frontend/editor/canvas/wireframes
frontend/editor/canvas/wireframes/components
frontend/editor/canvas/wireframes/logic
frontend/editor/component-library
frontend/editor/component-library/palette
frontend/editor/llm-control
frontend/editor/llm-control/agent-packet
frontend/editor/llm-control/agent-packet/components
frontend/editor/llm-control/editor-context
frontend/editor/llm-control/editor-context/components
frontend/editor/llm-control/project-memory
frontend/editor/llm-control/project-memory/components
frontend/editor/node-detail
frontend/editor/node-detail/assignment
frontend/editor/node-detail/assignment/components
frontend/editor/node-detail/components
frontend/editor/node-detail/content
frontend/editor/node-detail/content/components
frontend/editor/node-detail/content/logic
frontend/editor/node-detail/content/styles
frontend/editor/node-detail/journal
frontend/editor/node-detail/journal/components
frontend/editor/node-detail/links
frontend/editor/node-detail/links/components
frontend/editor/sector-detail
frontend/editor/workflow
frontend/editor/workflow/components
frontend/layout
frontend/layout/environment-switch
frontend/layout/environment-switch/components
frontend/layout/mode-rail
frontend/layout/mode-rail/components
frontend/layout/shell
frontend/layout/shell/styles
frontend/layout/top-bar
frontend/layout/top-bar/components
frontend/live-run
frontend/live-run/node-activity
frontend/live-run/node-activity/components
frontend/live-run/node-sessions
frontend/live-run/node-sessions/components
frontend/live-run/node-sessions/logic
frontend/live-run/node-sessions/styles
frontend/live-run/run-monitor
frontend/live-run/run-monitor/components
frontend/live-run/run-monitor/logic
frontend/live-run/run-monitor/styles
frontend/project
frontend/project-setup
frontend/project-setup/components
frontend/project-setup/styles
frontend/project/maps
frontend/project/maps/components
frontend/project/maps/styles
frontend/project/shell
frontend/project/shell/components
frontend/project/shell/styles
frontend/project/source-tree
frontend/project/source-tree/components
frontend/project/workspace
frontend/project/workspace/components
frontend/shared
frontend/shared/api
frontend/shared/contexts
frontend/shared/contexts/components
frontend/shared/desktop-state
frontend/shared/desktop-state/logic
frontend/shared/hooks
frontend/shared/hooks/logic
frontend/shared/selection
frontend/shared/selection/logic
frontend/shared/surface-settings
frontend/shared/surface-settings/logic
frontend/shared/types
frontend/shared/types/logic
frontend/ui-kit
frontend/ui-kit/panel-frame
frontend/ui-kit/panel-frame/styles
frontend/ui-kit/removal-dialog
frontend/ui-kit/removal-dialog/components
frontend/ui-kit/workspace-boundary
frontend/ui-kit/workspace-boundary/components
```
