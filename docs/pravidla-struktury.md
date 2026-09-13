# Pravidla struktury projektu

Tento dokument je autorita pro umístění nového souboru. Při pochybnosti se řídí tímto pořadím otázek.

```
opora-canvas/
  frontend/
    app/                # main.tsx, App.tsx, routing, theme bootstrap
    layout/
      shell/            # AppShell: levý bar · plátno · pravý bar
      top-bar/
      left-bar/         # PALETA: komponenty, funkce, metody k vložení
      right-bar/        # ŘÍZENÍ: Claude Code hooky, commands, agenti, běhy
      mode-rail/
    canvas/             # plátno: Board, hrany, vrstvy, drobečky, viewport
      sector-card/
      node-card/
      drawing/          # Excalidraw vrstva
    node-detail/        # UZEL · DETAIL
      content/          # Obsah (text)
      assignment/       # Zadání (cíl, ne-cíle, akceptace)
      work/             # Práce (fáze, kroky, důkazy)
      links/            # Souvislosti
      journal/
      packet/           # Podklady pro agenta
    sector-detail/      # stejná šablona jako node-detail
    project-detail/     # paměť projektu, nastavení, mapy (archify/graphify)
    library/            # UI knihovny předloh
    agents/             # UI běhů agentů, sessions, live run
    components/         # znovupoužitelné bez domény
      <name>/           # <Name>.tsx + <Name>.test.tsx + <name>.css
    shared/
      api/              # jeden klient nad backend API + typy odpovědí
      hooks/
      contexts/
      types/
    design/             # tokens.css, témata, fonty, obrázky, ikony

  backend/
    app/                # create_app, registrace routerů, middleware, origin guard
    api/                # tenké routery: project, sector, node, agents, library, claude, maps
    domain/
      project/          # project_hub, settings, workspaces
      sector/
      node/             # node_text, node_specs, node_links, node_journal, removals, node_sessions
      graph/            # graph.py, view, digest
    agents/
      control/          # rozhraní pro agenty (MCP server, viz §6)
      packets/          # context_packets, desktop_v3_packets, desktop_v3_state
      runs/             # coding_runs, coding_tools, llm_runs, task_handoffs, workery
      sources/          # agent_sources, agent_bindings, agent_activity, agent_telemetry, agent_catalog
    library/            # knihovna předloh: načtení, verze, checklisty, zpětná vazba
    claude_code/        # hooky, commands, skills řízené z aplikace
    maps/               # archify_*, graphify_*, map_refresh_*, map_artifacts
    integrations/       # gitio, workspace_sources, workspace_documents, build_identity
    (každý balíček má vlastní tests/)

  database/
    schema/             # SQL / migrace po tabulkách
    repositories/       # přístup k datům (vyčleněno ze service.py)
    seeds/              # výchozí obsah knihovny předloh

  library/              # DATA knihovny předloh, verzované v gitu
    components/<name>/  # blueprint.md + checklist.yaml + šablona kódu
    functions/
    methods/
    lessons/            # zaznamenané chyby → návrhy aktualizace předloh

  claude/               # co čte Claude Code: hooks/, commands/, skills/, CLAUDE.md
  shared/               # JSON schémata kontraktů FE ↔ BE ↔ agenti
  docs/                 # PRODUCT-CONTRACT, pravidla struktury, ADR, tento spec
  tools/                # build a dev skripty: copy-drawing-assets, serve-preview
  vendor/archify/
```

Pravidla umístění nového souboru:

1. Vidí to uživatel? → `frontend/`. Je to obecné (bez domény)? → `components/`. Patří to jednomu panelu nebo obrazovce? → příslušná doménová složka. Jinak `shared/`.
2. Je to logika, proces, integrace? → `backend/`. Router jen do `api/`, logika do `domain/`, `agents/`, `maps/` nebo `integrations/`.
3. Je to schéma nebo přístup k datům? → `database/`.
4. Je to předloha, checklist nebo poučení? → `library/`.
5. Test leží vedle toho, co testuje. Css leží vedle komponenty. Název souboru říká, co dělá a k čemu patří.

## Skutečný stav

```
backend
backend/agents
backend/agents/control
backend/agents/packets
backend/agents/runs
backend/agents/sources
backend/api
backend/app
backend/claude_code
backend/domain
backend/domain/graph
backend/domain/node
backend/domain/project
backend/domain/sector
backend/integrations
backend/library
backend/maps
frontend
frontend/agents
frontend/agents/desktop-v3
frontend/agents/panels
frontend/app
frontend/canvas
frontend/canvas/drawing
frontend/canvas/node-card
frontend/canvas/sector-card
frontend/components
frontend/components/removal-dialog
frontend/design
frontend/layout
frontend/layout/left-bar
frontend/layout/mode-rail
frontend/layout/right-bar
frontend/layout/shell
frontend/layout/top-bar
frontend/library
frontend/node-detail
frontend/node-detail/assignment
frontend/node-detail/content
frontend/node-detail/journal
frontend/node-detail/links
frontend/node-detail/packet
frontend/node-detail/work
frontend/project-detail
frontend/project-detail/inspector
frontend/project-detail/maps
frontend/project-detail/workspace
frontend/sector-detail
frontend/shared
frontend/shared/api
frontend/shared/contexts
frontend/shared/hooks
frontend/shared/types
```
