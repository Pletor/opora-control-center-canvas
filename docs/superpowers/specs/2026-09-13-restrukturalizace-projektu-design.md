# Restrukturalizace projektu Opora Canvas podle pravidel uzlu

Datum: 2026-09-13
Zdroj zadání: uzel „Struktura složek ve VSC" (`3aa5bd26-429a-444b-b9aa-b7606dbfb3ae`) a jeho poduzly Frontend, Backend, Databáze, Pojmenování souboru, Design v projektu „OPORA Control Center — vývoj aplikace" (workspace draft, náhled 8780).

## 1. Cíl

Vytvořit nový čistý worktree, do kterého se přenese **jen to, co skutečně používá náhled na http://127.0.0.1:8780/**, v nové složkové struktuře podle pravidel uzlu. Vše ostatní (laneové testy, důkazy, řídicí dokumenty agentů, mrtvý kód) se nepřenáší. Struktura zároveň připraví domov pro další rozvoj: řízení aplikace agenty přes MCP, levý bar s paletou, pravý bar s ovládáním Claude Code, knihovnu předloh s checklisty a učení z chyb.

Pravidla z uzlů, která struktura vynucuje:

- Oddělit, co vidí uživatel (CX/UX/UI), od logiky. Logika patří do backendu. Databáze a doplňkové technologie mají vlastní místo.
- Znovupoužitelné komponenty, metody a funkce: rodič → dítě → potomci. Hlavní složka komponenty obsahuje kód, test a css pohromadě.
- Frontend: layout, komponenty, knihovny a sdílené metody jsou globální a upravují se z jednoho místa; specializované věci jsou lokální.
- Design: stylování řešit globálně, soubory na svém místě.
- Pojmenování: BEM v CSS; názvy souborů jako příběh, dlouhé názvy nevadí.
- Každý uzel projektu má stejnou šablonu: podstata, obsah, zadání, práce, souvislosti, podklady pro agenta.

## 2. Ne-cíle

- Žádná změna chování aplikace během přesunu. Přesun je čistě strukturální; funkce se mění až po něm.
- Neměnit běžící procesy 8740 a 8768 ani worktree `opora-v3`, ze kterého 8780 dnes běží. Přepnutí 8780 na nový worktree je samostatný, potvrzovaný krok na konci.
- Neimplementovat MCP server, paletu, pravý bar ani knihovnu předloh v tomto kroku. Vytvoří se pouze jejich složky s README, které říkají, co tam patří.
- Nemazat `.data/` produkčních běhů. Nový worktree začíná s prázdným `.data/`.

## 3. Co je živé a co se maže

Zjištěno skenem dosažitelnosti ve worktree `C:/Users/Admin/opora-v3` (commit 372bb3d, shodný s main):

Přenáší se:

- `src/`: 78 z 82 souborů dosažitelných z `main.tsx`.
- `backend/`: všech 49 modulů. Šest modulů bez importu jsou subprocesové workery (`coding_worker`, `coding_oracle`, `graphify_worker`, `task_handoff_worker`, `task_handoff_tools`) spouštěné cestou k souboru.
- `vendor/archify` (používá `map_refresh_archify.py`).
- `scripts/copy-drawing-assets.mjs` (součást buildu), `index.html`, `public/`, `package.json`, `package-lock.json`, `tsconfig.json`, `pyproject.toml`, `uv.lock`, `vite.config.ts`.
- `tests/` (61 pytest): přenáší se jen ty, které testují přenesený kód, a to vedle testovaného balíčku.
- `PRODUCT-CONTRACT.md`, `README.md`, `START-HERE.md` do `docs/`.

Maže se (nepřenáší):

- Mrtvý kód: `src/MapTools.tsx`, `src/ProjectMap.tsx`, `src/project-map.ts`.
- 16 laneových `playwright.*.config.ts` a `playwright.config.ts`, všech 7 složek `e2e*`.
- `evidence/`, `test-results/`, `graphify-out/`, `.opora/`, `.claude/` (výjimka: skill `.claude/skills/opora-control-center` se přenáší do `claude/skills/`, protože je to první ovládání aplikace pro agenty).
- `verify-document-task-live-ui.cjs`, `vite.desktop-v3.config.ts`, `vite.workflow-drafts.config.ts`.
- Laneové skripty: `bind_node_session.py`, `inspect_runtime.py`, `prepare_e2e.py`, `production_snapshot.py`, `run_node_session_lane.py`, `serve_clean_editor_fixture.py`, `serve_v3_shell_fixture.py`.
- `dist/` (generuje se buildem).

## 4. Cílová struktura

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

## 5. Mapování stávajících souborů

Frontend (`src/` → `frontend/`):

| Dnes | Nově |
|---|---|
| main.tsx, App.tsx, style.css, DesktopThemeControls.tsx | app/ |
| TopBar.tsx, ModeRail.tsx, EnvironmentSwitch.tsx, ProjectLayout.tsx, EditorWorkbench.tsx, project-layout.css | layout/ (shell, top-bar, mode-rail) |
| Board.tsx, natural-canvas.css, LayerContext.tsx, DrawingWorkspace.tsx, DrawingTools.tsx, drawing-state.ts, drawing.css | canvas/ |
| NodePanel.tsx, NodeTextEditor.tsx, NodeSpecEditor.tsx, NodeJournal.tsx, NodeLinksPanel.tsx, NodeActivity.tsx, BlockOutline.tsx, block-commands.ts, TextWorkspace.tsx, text-workspace.css | node-detail/ |
| ProjectHome.tsx, ProjectWorkspace.tsx, project-home.css, ArchifyMap.tsx, GraphifyMap.tsx, MapUpdateMenu.tsx, map-update-menu.css, archify-map.css, AgentContextMap.tsx, agent-context-map.css, WireframeInspector.tsx, wireframe-model.ts, SourceExplorer.tsx | project-detail/ |
| AgentsWorkspace.tsx, agents.css, agent-types.ts, LiveRunDetail.tsx, CodingPanel.tsx, PlanPanel.tsx, TaskHandoffPanel.tsx, ContextShelf.tsx, context-actions.tsx, desktop-v3/* | agents/ |
| RemovalDialog.tsx | components/removal-dialog/ |
| ScopeContext.tsx, use-pending-edits.ts, types.ts, vite-env.d.ts | shared/ |
| desktop-v3.css, desktop-workspaces.css | design/ (globální části) nebo k příslušné komponentě |

Backend (`backend/` → balíčky podle §4). `app.py` se rozdělí: registrace do `app/`, routery zůstanou tenké v `api/`. `service.py` (CanvasService) se přesune do `domain/` a datový přístup postupně do `database/repositories/`, ale v tomto kroku pouze přesun, ne rozdělení.

Podrobné mapování backendu a testů je součástí implementačního plánu.

## 6. Rozhraní pro agenty (rezervováno, neimplementuje se nyní)

Agenti (Claude Code, Codex, Hermes) ovládají aplikaci přes **MCP server** v `backend/agents/control/`. Plánované nástroje: `get_tree(scope)`, `get_node`, `get_sector`, `get_project`, `claim_task`, `report_result`, `add_evidence`, `list_library`, `get_checklist`, `record_lesson`. `claude/` obsahuje hooky a commands, které tyto nástroje volají. Rozsah `scope` má hodnoty `node`, `subtree`, `lineage`, aby agent dostal buď izolovaný uzel, nebo celý strom.

## 7. Postup a bezpečnost

1. Nový worktree `restructure/clean-core` z main (372bb3d) v `C:/Users/Admin/opora-clean`. Nic se nedělá v `opora-v3` ani na mainu.
2. Přesun po vrstvách, každá vrstva = jeden commit: (a) smazání balastu, (b) frontend, (c) backend, (d) database + shared + library + claude + docs + tools skelet, (e) testy vedle kódu.
3. Po každém kroku: `tsc --noEmit`, `vite build`, `pytest`, `ruff`. Start backendu na volném portu a ruční kontrola, že plátno, detail uzlu a podklady pro agenta fungují.
4. Přepnutí 8780 na nový worktree až po potvrzení uživatelem; do té doby 8780 běží beze změny.

## 8. Podmínky dokončení

- Kořen worktree obsahuje jen složky z §4 plus konfigurační soubory (`package.json`, `pyproject.toml`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.gitignore`).
- Build frontendu a backendu prochází, přenesené pytest testy jsou zelené.
- Aplikace z nového worktree otevře projekt „OPORA Control Center — vývoj aplikace" nad kopií dat a zobrazí uzel Struktura složek ve VSC se všemi poduzly.
- Každá složka z §4 má README.md s jednou větou, co do ní patří.
- Dokument `docs/pravidla-struktury.md` obsahuje pravidla umístění z §4.
