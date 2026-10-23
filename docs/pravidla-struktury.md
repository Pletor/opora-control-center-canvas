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
      editor/           # canvas_routes, node_routes, desktop_v3_routes, claude_code_routes
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

## Kontrola struktury

Skutečný stav se nepíše ručně: strom ukáže Glob nebo průzkumník a pravidla výše hlídá
`tools/structure_check.py`. Seznam porušení vypíše `uv run python tools/structure_check.py`
(řádek = pravidlo, cesta, důvod); `npm run verify` z něj dělá ráčnu `STRUCTURE_BASELINE`
v `tools/verify.py`: počet nálezů pravidla smí jen klesat a pravidlo, které v ráčně chybí, má nulu.

| Pravidlo | Co hlídá |
|---|---|
| `supliky` | `.tsx` v `components/`, `.ts` v `logic/` (test `.test.ts` i vedle komponenty), `.css` ve `styles/` |
| `testy-vedle` | žádné složky `tests/`, `test/`, `__tests__/` ve `frontend/`, `backend/`, `database/`, `tools/` |
| `router-v-api` | `APIRouter(` jen v `backend/api/` |
| `nazev` | žádné složky ani soubory `utils`, `misc`, `common`, `helpers` |
| `readme` | feature složka frontendu (má `components/`, `logic/` nebo `styles/`) a balíček backendu či databáze mají `README.md` |
| `delka` | zdrojový soubor mimo testy má nejvýš 200 řádků; dnes ráčna, dělí se při další změně souboru |
