# Pravidla struktury projektu

Tento dokument je autorita pro umístění nového souboru. Při pochybnosti se řídí tímto pořadím otázek.

```
opora-canvas/
  frontend/             # cesta uživatele: nastavení → Projekt | Editor | OporaHub
    app/                # main.tsx, App.tsx, theme, barrel panelů (skládání prostředí)
    design-tokens/      # theme-tokens.css: barvy, témata, hustota
    layout/             # kostra obrazovky společná všem prostředím
      top-bar/
      environment-switch/ # Projekt | Editor | OporaHub (Alt+1..3)
      mode-rail/        # módy plátna uvnitř Editoru (vodorovné záložky ve druhé řadě lišty)
      panel-dock/       # menu Editoru ☰: lišta Struktura | Schránka | Nastavení a panel sekce vedle ní
      account-corner/   # levý dolní roh: tlačítko Opora a popup menu
      shell/            # styly pracovní plochy
    project-setup/      # KROK 1: přiřazení repozitářů a složek, vytvoření projektu
    project/            # PROSTŘEDÍ PROJEKT: pohled na main
      shell/            # levý strom + navigace map (ProjectLayout)
      source-tree/      # strom složek a souborů (SourceExplorer)
      maps/             # Archify, Graphify, obnova map
      workspace/        # složení plochy, dokumentace k cestám
    editor/             # PROSTŘEDÍ EDITOR: řízení vývoje
      canvas/           # board, drawing (Excalidraw), wireframes, node-card, sector-card, history (krok zpět, Ctrl+Z)
      node-detail/      # NodePanel: content, assignment, process (návrh → proces → hotovo → oprava), journal, links, agent-summary (souhrn práce agentů v módu Text)
      sector-detail/    # stejná šablona jako node-detail
      workflow/         # fáze, kritéria, kroky uzlu → základ pipeline
      component-library/ # LEVÁ STRANA: knihovna komponent, metod, funkcí (palette/)
      llm-control/      # PRAVÁ STRANA: Claude Code skills, commandy, agenti
        project-memory/ # pravidla, rozhodnutí, nastavení
        editor-context/ # reference a „úkol pro agenta“
        agent-packet/   # podklady pro agenta: náhled, snímek, export
    hub/                # PROSTŘEDÍ OPORAHUB: plán a dokumentace 1:1 s kódem
      oporahub-workspace/ # panel synchronizace (Oracle verdikt, echo)
    shared/             # bez závislosti na prostředích
      api/              # slot: jeden klient nad backend API
      types/  hooks/  contexts/
      desktop-state/    # stav panelů (paměť, workflow, podklady)
      selection/        # vybraný zdroj, reference, poznámka
      surface-settings/ # mřížka, přichytávání, mód
    settings/           # nastavení aplikace z levého dolního rohu: Obecné, Plátno, Projekt, Skills (Claude Code), Connectors
    ui-kit/             # prvky bez domény: removal-dialog, workspace-boundary, panel-frame
    (uvnitř každé feature složky: components/ = .tsx · logic/ = .ts · styles/ = .css · README)

  backend/              # stejný příběh jako frontend; api → prostředí → canvas, integrations
    app/                # create_app, middleware, mount dist/, skládání routerů z api/
    api/                # ROBUSTNÍ API: tenké routery podle prostředí; app_routes = zdraví, identita, bootstrap
      project_setup/    # project_routes: nastavení, lokální/prázdný projekt, connect
      project/          # project_workspace_routes, workspace_routes, archify_routes, graphify_routes, map_refresh_routes
      editor/           # canvas_routes, node_routes, desktop_v3_routes, claude_code_routes, process_routes
    canvas/             # základ plátna: canvas_service (registr + db_for(projekt), git sync, graf), graph, project_folder (projects/<id>/), project_registry, migrate_to_project_folders
    project_setup/      # KROK 1: project_hub (připojení repozitáře, založení projektu)
    project/            # PROSTŘEDÍ PROJEKT
      workspace/        # strom zdrojů, otevírání souborů, dokumentace k cestám
      worktrees/        # workspace_domain (worktree ↔ doména), workspace_archive (skladiště uzavřených worktree)
      maps/             # graphify, archify, map_refresh, artefakty, snapshoty
    editor/             # PROSTŘEDÍ EDITOR: obsah uzlů a vše, co dostává agent
      node/             # node_text, node_specs, node_journal, node_links, drawings, wireframe_context, removals
      sector/           # slot: zpracování celého sektoru
      agent_memory/     # desktop_v3_state: pravidla, rozhodnutí, fáze uzlu
      agent_packet/     # desktop_v3_packets, redact: podklady pro agenta
      agent_handoff/    # external_agent_tasks: předání úkolu externímu agentovi
      process/          # process_store, process_lifecycle (návrh → proces → hotovo → oprava), process_reports (odpovědi agentů)
      task_execution/   # slot: vykonání úkolu z uzlu podle ID
    memory/             # paměť agenta podle role napříč projekty (OpenViking): roles, memory_service
    integrations/       # platforma: gitio, windows_job, build_identity, openviking_client
    claude_code/        # skills_catalog (SKILL.md z projektu, uživatele, pluginů), skill_preferences (vypnuté skills); commands přibudou
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
    agent-roles.json    # role agenta (frontend, backend, databáze…): id, název, popis

  .claude/              # co čte Claude Code: hooks/, commands/, skills/ (opora-control-center, prompt-master)
  shared/               # JSON schémata kontraktů FE ↔ BE ↔ agenti
  docs/                 # PRODUCT-CONTRACT, pravidla struktury, ADR, tento spec
  tools/                # build a dev skripty: copy-drawing-assets, serve-preview
  vendor/archify/
```

Pravidla umístění nového souboru:

1. Vidí to uživatel? → `frontend/`. Kde v cestě uživatele to je? → `project-setup/`, `project/`, `editor/` nebo `hub/`. Je to obecné (bez domény)? → `ui-kit/`. Sdílený stav bez závislosti na prostředí? → `shared/`. Uvnitř složky: .tsx do `components/`, .ts do `logic/`, .css do `styles/`.
2. Je to logika, proces, integrace? → `backend/`. Kde v cestě uživatele to je? → `project_setup/`, `project/`, `editor/`. Router jen do `api/<prostředí>/`. Základ plátna → `canvas/`, platforma → `integrations/`.
3. Je to schéma nebo přístup k datům? → `database/`.
4. Je to předloha, checklist nebo poučení? → `library/`.
5. Test leží hned vedle toho, co testuje, jako `test_<modul>.py` (backend) nebo `<name>.test.ts` (frontend, běží `npm test` = vitest); žádné složky tests/. Css leží ve `styles/` vedle komponenty. Název souboru říká, co dělá a k čemu patří.

## Skládání frontendu: rodič skládá dílky, události bublají nahoru

Každý viditelný celek (karta, blok, panel, záložka) je **složka feature** s vlastním `README.md` a podsložkami `components/`, `logic/`, `styles/`. Uvnitř platí:

1. **Jeden rodič, malé dílky.** Rodičovská komponenta (`NodeCard`, `CanvasBlock`, `NodeTree`) importuje dílky a skládá je. Dílek (`CardHead`, `BlockTodos`, `BlockState`…) zobrazuje jednu část a nic neví o plátně, API ani o ostatních dílcích. Žádný soubor nemá být delší než zhruba 200 řádků; když roste, vzniká další dílek.
2. **Data tečou dolů, události nahoru.** Dílek dostává hotová data v props a každou změnu hlásí callbackem (`onToggle`, `onAddTodo`, `onBranch`). Kdo ukládá, rozhoduje rodič: on drží `useDesktopState`, zámek zápisu a revizi. Dílek nikdy nevolá `mutate` ani `fetch`.
3. **Logika bez Reactu do `logic/`.** Odvození dat a mutace stavu jsou čisté funkce (`card-model.ts`, `block-model.ts`, `tree-model.ts`) s testem `<name>.test.ts` hned vedle. Komponenta je jen mapování props → JSX.
4. **Styl na dílek, BEM, příběhově popsaný.** Jeden `styles/<feature>.css` na složku. Třídy podle BEM: blok = feature (`node-card`), prvek = `blok__prvek` (`node-card__title`, `node-card__port`), varianta = `blok__prvek--stav` (`node-card__port--open`, `node-card--sector`). Blok se stylizuje jen svými třídami: žádné selektory na `strong`/`p`/`li` uvnitř bloku, žádné vnoření přes tři úrovně, žádný `!important`. Tokeny barev a rytmu jen z `design-tokens/`. Každý blok v souboru začíná komentářem, který vypráví, co uživatel vidí a proč (například „Karta je 360 široká, aby se dalo číst zadání bloků; porty jsou kuličky na pravé hraně, protože z nich se táhne vazba“), ne co selektor technicky dělá. Kdo čte jen CSS, musí z komentářů pochopit celý dílek.
5. **Změna jednoho dílku nerozbije celek.** Když se mění jen akce, pravidla, stav nebo další krok, sahá se jen do jejich složky; rodič se mění jen tehdy, když přibývá nový dílek nebo nová událost.

Příklady: `frontend/editor/canvas/node-card/` (karta), `frontend/editor/workflow/blocks/` (bloky Akce / Pravidla), `frontend/editor/workflow/pipeline-picker/`, `frontend/editor/node-detail/tree/` (strom obsahu), `frontend/editor/canvas/tag-filter/`.

## Jedno rozhraní pro všechny projekty

Rozhraní je jedno pro celou aplikaci. Vzhled (barevný režim, hustota, tokeny v `design-tokens/`) a ovládání (mřížka, přichytávání, vypnuté skills) se ukládají jednou pro aplikaci, nikdy s klíčem projektu. Per projekt se ukládá jen obsah: graf, poloha plátna, paměť projektu, cíl a platforma.

Když se má chování lišit, liší se podle **druhu projektu**, ne podle konkrétního projektu, a to na jediném místě: `frontend/shared/project-capabilities/logic/project-capabilities.ts`. Rodič (`App`) schopnosti spočítá a rozdá dílkům v props; dílek nikdy nečte `sourceKind` ani `project === "draft"` sám. Nová větev chování = nové pole ve schopnostech + test, ne další podmínka v komponentě.

Audit stavu k 2026-09-15: `docs/ux-central-audit.md`.

## Skutečný stav

```
backend
backend/api
backend/api/editor
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
backend/memory
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
frontend/editor/node-detail/agent-summary
frontend/editor/node-detail/agent-summary/components
frontend/editor/node-detail/agent-summary/logic
frontend/editor/node-detail/agent-summary/styles
frontend/editor/node-detail/agent-workspace
frontend/app/access-gate
frontend/app/access-gate/components
frontend/app/access-gate/logic
frontend/app/access-gate/styles
frontend/editor/node-detail/agent-workspace/memory
frontend/editor/node-detail/agent-workspace/memory/components
frontend/editor/node-detail/agent-workspace/memory/logic
frontend/editor/node-detail/agent-workspace/memory/styles
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
frontend/hub
frontend/hub/oporahub-workspace
frontend/hub/oporahub-workspace/components
frontend/hub/oporahub-workspace/logic
frontend/hub/oporahub-workspace/styles
frontend/layout
frontend/layout/environment-switch
frontend/layout/environment-switch/components
frontend/layout/mode-rail
frontend/layout/mode-rail/components
frontend/layout/panel-dock
frontend/layout/panel-dock/components
frontend/layout/panel-dock/logic
frontend/layout/panel-dock/styles
frontend/layout/shell
frontend/layout/shell/styles
frontend/layout/top-bar
frontend/layout/top-bar/components
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
