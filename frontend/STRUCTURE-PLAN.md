# Plán struktury `frontend/` (fáze 1 – návrh v2, čeká na schválení)

Cíl: strom složek vypráví příběh aplikace. Kdo ho otevře, vidí cestu uživatele:
**nastavení projektu → prostředí Projekt | Editor | OporaHub**, každé se svými nástroji.
Uvnitř každé feature složky jsou soubory rozdělené podle druhu do pevných šuplíků.
Chování aplikace se nemění; mění se jen cesty, názvy složek, názvy čtyř souborů a import řádky.

## 0. Příběh aplikace, který strom kopíruje

| Krok uživatele | Co dělá | Složka |
|---|---|---|
| 1. Úvodní nastavení | přiřadí repozitáře nebo složky, vytvoří projekt | `project-setup/` |
| 2. Prostředí **Projekt** | vidí main skrz strom složek, Graphify a další vývojová zobrazení | `project/` |
| 3. Prostředí **Editor** | řídí vývoj: plátno, detail uzlu, workflow a pipeline; vlevo knihovna komponent, metod a funkcí; vpravo ovládání Claude Code (skills, commandy, agenti, paměť) | `editor/` |
| 4. Prostředí **OporaHub** | plán a dokumentace 1:1 s kódem (panel synchronizace) | `hub/` |
| společné | vstup aplikace, kostra obrazovky, přepínač prostředí, tokeny vzhledu, sdílený stav, prvky bez domény | `app/`, `layout/`, `design-tokens/`, `shared/`, `ui-kit/` |

## 1. Pravidla

### 1.1 Šuplíky uvnitř každé feature složky
| Šuplík | Co obsahuje |
|---|---|
| `components/` | React komponenty (`.tsx`) |
| `logic/` | čisté TypeScript soubory bez JSX (`.ts`): stav, API volání, typy, příkazy, deklarace |
| `styles/` | `.css` (šuplík existuje jen tam, kde feature CSS opravdu má) |
| `README.md` | první věta říká, co složka zobrazuje a odkud bere data |

Složka obsahuje buď jen podsložky + README, nebo soubory jednoho druhu.

### 1.2 Pojmenování složek
- anglicky, kebab-case, podstatné jméno popisující obrazovku nebo funkci
- NIKDY `utils`, `misc`, `common`, `helpers`, `panels`, `components` jako název feature, verze (`v2`, `v3`)

### 1.3 Pravidlo závislostí
- `shared/` a `ui-kit/` nesmí importovat z `project-setup/`, `project/`, `editor/`, `hub/`, `layout/`, `app/`
- `app/` je jediné místo, které skládá všechna prostředí dohromady

### 1.4 Co se NEDĚLÁ
- žádná změna obsahu komponent, logiky, exportů ani CSS pravidel
- žádné mazání; složky, které mají jen README, zůstávají jako plánované sloty (§4)
- přesun výhradně `git mv`

## 2. Cílový strom

```
frontend/
├── README.md
├── STRUCTURE-PLAN.md
│
├── app/                               vstup aplikace a skládání prostředí dohromady
│   ├── components/  App.tsx · DesktopThemeControls.tsx · main.tsx
│   ├── logic/       vite-env.d.ts · desktop-panels.ts   (barrel panelů, dříve agents/desktop-v3/index.ts)
│   └── styles/      style.css
│
├── design-tokens/                     barvy, hustota, témata (:root tokeny)
│   └── styles/      theme-tokens.css                    (dříve design/desktop-v3.css)
│
├── layout/                            kostra obrazovky společná všem prostředím
│   ├── top-bar/            components/TopBar.tsx
│   ├── environment-switch/ components/EnvironmentSwitch.tsx   Projekt | Editor | OporaHub (Alt+1..3)
│   ├── mode-rail/          components/ModeRail.tsx            módy plátna uvnitř Editoru
│   └── shell/              styles/desktop-workspaces.css · workspace-modes.css
│
├── project-setup/                     KROK 1: přiřazení repozitářů a složek, vytvoření projektu
│   ├── components/  ProjectHome.tsx
│   └── styles/      project-home.css
│
├── project/                           PROSTŘEDÍ PROJEKT: pohled na main
│   ├── shell/       components/ProjectLayout.tsx          levý strom + navigace map
│   │                styles/project-layout.css
│   ├── source-tree/ components/SourceExplorer.tsx         strom složek a souborů projektu
│   ├── maps/        components/GraphifyMap.tsx · MapUpdateMenu.tsx
│   │                styles/map-view.css · map-update-menu.css
│   └── workspace/   components/ProjectWorkspace.tsx
│
├── editor/                            PROSTŘEDÍ EDITOR: řízení vývoje
│   ├── canvas/                        plátno
│   │   ├── board/       components/Board.tsx
│   │   ├── drawing/     components/DrawingTools.tsx · DrawingWorkspace.tsx
│   │   │                logic/drawing-state.ts
│   │   │                styles/drawing.css
│   │   ├── wireframes/  components/WireframeTools.tsx · WireframeInspector.tsx · WireframePreview.tsx
│   │   │                logic/wireframe-model.ts
│   │   ├── settings/    components/WorkspaceSettings.tsx    dialog mřížky a přichytávání
│   │   ├── node-card/   README (slot)
│   │   └── sector-card/ README (slot)
│   ├── node-detail/                   inspektor uzlu
│   │   ├── components/  NodePanel.tsx · LayerContext.tsx
│   │   ├── content/     components/TextWorkspace.tsx · NodeTextEditor.tsx · BlockOutline.tsx
│   │   │                logic/block-commands.ts
│   │   │                styles/text-workspace.css · block-outline.css
│   │   ├── assignment/  components/NodeSpecEditor.tsx
│   │   ├── journal/     components/NodeJournal.tsx
│   │   └── links/       components/NodeLinksPanel.tsx
│   ├── sector-detail/   README (slot)
│   ├── workflow/        components/NodeWorkflowPanel.tsx    fáze, kritéria, kroky uzlu → základ pipeline
│   ├── component-library/             LEVÁ STRANA: knihovna komponent, metod, funkcí
│   │   ├── README (slot, dříve library/)
│   │   └── palette/ README (slot, dříve layout/left-bar/)
│   └── llm-control/                   PRAVÁ STRANA: ovládání Claude Code
│       ├── README (dříve layout/right-bar/)              skills, commandy, agenti
│       ├── project-memory/  components/ProjectMemoryPanel.tsx   pravidla, rozhodnutí, nastavení
│       ├── editor-context/  components/ContextShelf.tsx · context-actions.tsx  reference a „úkol pro agenta“
│       └── agent-packet/    components/AgentPacketPanel.tsx     podklady pro agenta: náhled, snímek, export
│
├── hub/                               PROSTŘEDÍ OPORAHUB: plán a dokumentace 1:1 s kódem
│   └── oporahub-workspace/  components/ · logic/ · styles/   panel synchronizace (Oracle verdikt, echo)
│
├── shared/                            sdílený stav a typy, bez závislosti na prostředích
│   ├── api/              README (slot – klient `api()` zatím žije v types/types.ts, §4)
│   ├── types/            logic/types.ts · workspace-mode.ts
│   ├── hooks/            logic/use-pending-edits.ts
│   ├── contexts/         components/ScopeContext.tsx
│   ├── desktop-state/    logic/api.ts · state-store.ts · types.ts   stav panelů (paměť, workflow, podklady)
│   ├── selection/        logic/workspace-selection.ts               vybraný zdroj, reference, poznámka
│   └── surface-settings/ logic/workspace-settings.ts                mřížka, přichytávání, aktuální mód
│
└── ui-kit/                            prvky bez domény
    ├── removal-dialog/     components/RemovalDialog.tsx
    ├── workspace-boundary/ components/WorkspaceBoundary.tsx      error boundary „workspace nedostupný“
    └── panel-frame/        styles/panels.css                     společný rám panelů
```

## 3. Tabulka přesunů (všech 108 souborů)

Legenda: **R** = přejmenování složky/cesty, **RN** = přejmenování souboru (4 případy), **=** = zůstává.

### app/ a design/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| README.md | README.md | = (doplnit příběh z §0) |
| app/README.md | app/README.md | = |
| app/App.tsx | app/components/App.tsx | šuplík |
| app/DesktopThemeControls.tsx | app/components/DesktopThemeControls.tsx | šuplík |
| app/main.tsx | app/components/main.tsx | vstup; cesta v index.html se přepíše |
| app/vite-env.d.ts | app/logic/vite-env.d.ts | deklarace = logika |
| app/style.css | app/styles/style.css | šuplík |
| agents/desktop-v3/index.ts | app/logic/desktop-panels.ts | RN; barrel skládá panely z editoru, patří ke skládání v app/ |
| design/README.md | design-tokens/README.md | R; složka má jen tokeny |
| design/desktop-v3.css | design-tokens/styles/theme-tokens.css | RN; definuje tokeny témat, „desktop-v3“ nic neříká |

### layout/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| layout/README.md | layout/README.md | = (text aktualizovat) |
| layout/top-bar/README.md | layout/top-bar/README.md | = |
| layout/top-bar/TopBar.tsx | layout/top-bar/components/TopBar.tsx | šuplík |
| layout/mode-rail/README.md | layout/mode-rail/README.md | = (text: jen módy plátna) |
| layout/mode-rail/ModeRail.tsx | layout/mode-rail/components/ModeRail.tsx | šuplík |
| layout/mode-rail/EnvironmentSwitch.tsx | layout/environment-switch/components/EnvironmentSwitch.tsx | přepínač Projekt/Editor/OporaHub je hlavní osa příběhu, zaslouží vlastní složku |
| – | layout/environment-switch/README.md | nový README |
| layout/shell/README.md | layout/shell/README.md | = (text aktualizovat) |
| layout/shell/desktop-workspaces.css | layout/shell/styles/desktop-workspaces.css | šuplík |
| layout/shell/ProjectLayout.tsx | project/shell/components/ProjectLayout.tsx | strom + navigace map je kostra prostředí Projekt |
| layout/shell/project-layout.css | project/shell/styles/project-layout.css | dtto |
| project-detail/workspace/workspace-modes.css | layout/shell/styles/workspace-modes.css | styly mode-rail, karet map a nástrojů kreslení; importuje App |
| layout/left-bar/README.md | editor/component-library/palette/README.md | levá strana patří Editoru (§0) |
| layout/right-bar/README.md | editor/llm-control/README.md | pravá strana patří Editoru (§0) |

### project-setup/ (krok 1)
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| project-detail/ProjectHome.tsx | project-setup/components/ProjectHome.tsx | výběr, připojení a vytvoření projektu = úvodní nastavení |
| project-detail/project-home.css | project-setup/styles/project-home.css | dtto |
| – | project-setup/README.md | nový README |

### project/ (prostředí Projekt)
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| project-detail/README.md | project/README.md | R; text přepsat podle §0 |
| project-detail/inspector/README.md | project/source-tree/README.md | R; text jen o stromu zdrojů |
| project-detail/inspector/SourceExplorer.tsx | project/source-tree/components/SourceExplorer.tsx | strom složek projektu |
| project-detail/maps/README.md | project/maps/README.md | R |
| project-detail/maps/GraphifyMap.tsx | project/maps/components/GraphifyMap.tsx | šuplík |
| project-detail/maps/MapUpdateMenu.tsx | project/maps/components/MapUpdateMenu.tsx | šuplík |
| project-detail/maps/archify-map.css (dnes map-view.css) | project/maps/styles/map-view.css | šuplík |
| project-detail/maps/map-update-menu.css | project/maps/styles/map-update-menu.css | šuplík |
| project-detail/workspace/README.md | project/workspace/README.md | R |
| project-detail/ProjectWorkspace.tsx | project/workspace/components/ProjectWorkspace.tsx | skládá shell + mapy |
| – | project/shell/README.md | nový README |

### editor/canvas/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| canvas/README.md | editor/canvas/README.md | R |
| canvas/Board.tsx | editor/canvas/board/components/Board.tsx | React Flow plátno |
| canvas/drawing/README.md | editor/canvas/drawing/README.md | R |
| canvas/drawing/DrawingTools.tsx | editor/canvas/drawing/components/DrawingTools.tsx | šuplík |
| canvas/drawing/DrawingWorkspace.tsx | editor/canvas/drawing/components/DrawingWorkspace.tsx | šuplík |
| canvas/drawing/drawing-state.ts | editor/canvas/drawing/logic/drawing-state.ts | šuplík |
| canvas/drawing/drawing.css | editor/canvas/drawing/styles/drawing.css | šuplík |
| project-detail/inspector/WireframeTools.tsx | editor/canvas/wireframes/components/WireframeTools.tsx | používá jen kreslení |
| project-detail/inspector/WireframeInspector.tsx | editor/canvas/wireframes/components/WireframeInspector.tsx | dtto |
| project-detail/inspector/WireframePreview.tsx | editor/canvas/wireframes/components/WireframePreview.tsx | dtto |
| project-detail/inspector/wireframe-model.ts | editor/canvas/wireframes/logic/wireframe-model.ts | dtto |
| project-detail/workspace/WorkspaceSettings.tsx | editor/canvas/settings/components/WorkspaceSettings.tsx | dialog mřížky a přichytávání plátna |
| canvas/node-card/README.md | editor/canvas/node-card/README.md | R slot |
| canvas/sector-card/README.md | editor/canvas/sector-card/README.md | R slot |
| – | editor/canvas/board/README.md, wireframes/README.md, settings/README.md | nové README |

### editor/node-detail/, sector-detail/, workflow/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| node-detail/README.md | editor/node-detail/README.md | R (text aktualizovat) |
| node-detail/NodePanel.tsx | editor/node-detail/components/NodePanel.tsx | šuplík |
| canvas/LayerContext.tsx | editor/node-detail/components/LayerContext.tsx | skládá journal + links uzlu, ne plátno |
| node-detail/content/README.md | editor/node-detail/content/README.md | R |
| node-detail/content/TextWorkspace.tsx | editor/node-detail/content/components/TextWorkspace.tsx | šuplík |
| node-detail/content/NodeTextEditor.tsx | editor/node-detail/content/components/NodeTextEditor.tsx | šuplík |
| node-detail/content/BlockOutline.tsx | editor/node-detail/content/components/BlockOutline.tsx | šuplík |
| node-detail/content/block-commands.ts | editor/node-detail/content/logic/block-commands.ts | šuplík |
| node-detail/content/text-workspace.css | editor/node-detail/content/styles/text-workspace.css | šuplík |
| canvas/natural-canvas.css | editor/node-detail/content/styles/block-outline.css | RN; používají ho jen editory bloků |
| node-detail/assignment/README.md | editor/node-detail/assignment/README.md | R |
| node-detail/assignment/NodeSpecEditor.tsx | editor/node-detail/assignment/components/NodeSpecEditor.tsx | šuplík |
| node-detail/journal/README.md | editor/node-detail/journal/README.md | R |
| node-detail/journal/NodeJournal.tsx | editor/node-detail/journal/components/NodeJournal.tsx | šuplík |
| node-detail/links/README.md | editor/node-detail/links/README.md | R |
| node-detail/links/NodeLinksPanel.tsx | editor/node-detail/links/components/NodeLinksPanel.tsx | šuplík |
| sector-detail/README.md | editor/sector-detail/README.md | R slot |
| agents/desktop-v3/NodeWorkflowPanel.tsx | editor/workflow/components/NodeWorkflowPanel.tsx | fáze a kritéria uzlu jsou zárodek workflow/pipeline z §0 |
| – | editor/workflow/README.md | nový README |

### editor/component-library/ a editor/llm-control/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| library/README.md | editor/component-library/README.md | R; levá knihovna komponent, metod, funkcí |
| agents/desktop-v3/ProjectMemoryPanel.tsx | editor/llm-control/project-memory/components/ProjectMemoryPanel.tsx | paměť a pravidla pro LLM = pravá strana Editoru |
| agents/panels/README.md | editor/llm-control/editor-context/README.md | R |
| agents/panels/ContextShelf.tsx | editor/llm-control/editor-context/components/ContextShelf.tsx | reference pro agenta |
| agents/panels/context-actions.tsx | editor/llm-control/editor-context/components/context-actions.tsx | „úkol pro agenta“ (.tsx, má AgentTaskNotice) |
| node-detail/packet/README.md | editor/llm-control/agent-packet/README.md | R; slot se naplní |
| agents/desktop-v3/AgentPacketPanel.tsx | editor/llm-control/agent-packet/components/AgentPacketPanel.tsx | podklady pro agenta = vstup práce s LLM |
| – | editor/llm-control/project-memory/README.md | nový README |

### shared/
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| shared/README.md | shared/README.md | = (doplnit pravidlo §1.3) |
| shared/api/README.md | shared/api/README.md | = slot (§4) |
| shared/types/README.md | shared/types/README.md | = |
| shared/types/types.ts | shared/types/logic/types.ts | šuplík |
| shared/types/workspace-mode.ts | shared/types/logic/workspace-mode.ts | šuplík |
| shared/hooks/README.md | shared/hooks/README.md | = |
| shared/hooks/use-pending-edits.ts | shared/hooks/logic/use-pending-edits.ts | šuplík |
| shared/contexts/README.md | shared/contexts/README.md | = |
| shared/contexts/ScopeContext.tsx | shared/contexts/components/ScopeContext.tsx | šuplík |
| agents/desktop-v3/README.md | shared/desktop-state/README.md | R; zbývá stav sdílený panely v editoru i hubu |
| agents/desktop-v3/api.ts | shared/desktop-state/logic/api.ts | importuje jen shared/types |
| agents/desktop-v3/state-store.ts | shared/desktop-state/logic/state-store.ts | dtto |
| agents/desktop-v3/types.ts | shared/desktop-state/logic/types.ts | dtto |
| project-detail/workspace/workspace-selection.ts | shared/selection/logic/workspace-selection.ts | používá project, editor i app; žádné feature importy |
| project-detail/workspace/workspace-settings.ts | shared/surface-settings/logic/workspace-settings.ts | používá layout, editor i app; importuje jen shared/types |
| – | shared/selection/README.md, shared/surface-settings/README.md | nové README |

### ui-kit/ (dříve components/)
| Stará cesta | Nová cesta | Proč |
|---|---|---|
| components/README.md | ui-kit/README.md | R; „components“ koliduje s názvem šuplíku |
| components/removal-dialog/README.md | ui-kit/removal-dialog/README.md | R |
| components/removal-dialog/RemovalDialog.tsx | ui-kit/removal-dialog/components/RemovalDialog.tsx | šuplík |
| project-detail/workspace/WorkspaceBoundary.tsx | ui-kit/workspace-boundary/components/WorkspaceBoundary.tsx | obecný error boundary bez domény |
| agents/desktop-v3/panels.css | ui-kit/panel-frame/styles/panels.css | společný rám .v3-panel pro 3 panely v různých prostředích |
| – | ui-kit/workspace-boundary/README.md, panel-frame/README.md | nové README |

Kontrolní součet: 108 původních souborů, 0 smazaných, 4 přejmenované soubory, 16 nových README.
Zanikají složky: `agents/`, `canvas/`, `components/`, `design/`, `library/`, `node-detail/` (kořen), `project-detail/`, `sector-detail/` (kořen), `layout/left-bar`, `layout/right-bar` – všechny jejich soubory jsou přesunuty, nic smazáno.

## 4. Složky jen s README (sloty)

| Slot | Rozhodnutí |
|---|---|
| editor/llm-control/agent-packet | **naplnit** AgentPacketPanel.tsx |
| editor/component-library, editor/component-library/palette | zachovat; kód knihovny zatím neexistuje, složka drží místo pro levou stranu Editoru |
| editor/llm-control (kořen) | zachovat; README popíše skills, commandy, agenty; podsložky project-memory, editor-context, agent-packet už kód mají |
| editor/canvas/node-card, sector-card | zachovat; karta je dnes uvnitř Board.tsx, vyjmutí = refaktor mimo rozsah |
| editor/sector-detail | zachovat; žádný kód |
| shared/api | zachovat; `api()` žije v shared/types/logic/types.ts, vyjmutí = změna obsahu souboru; doporučený další krok |

## 5. Co se po přesunu musí přepsat

### 5.1 Konfigurace a vstupy
| Soubor | Změna |
|---|---|
| index.html:25 | `/frontend/app/main.tsx` → `/frontend/app/components/main.tsx` |
| vite.config.ts, tsconfig.json, package.json, tools/copy-drawing-assets.mjs | beze změny (alias `@` = `./frontend` zůstává) |

### 5.2 Import řádky (všechny používají alias `@/…`, žádné relativní)
Přepsat podle §3 ve všech 44 souborech s importy. Nejcitlivější body:
- `app/components/App.tsx`: 34 importů včetně lazy `@/editor/canvas/drawing/components/DrawingWorkspace`
- `app/components/main.tsx`: `@/agents/desktop-v3` → `@/app/logic/desktop-panels`
- `app/logic/desktop-panels.ts`: 3 panely v `editor/llm-control/project-memory`, `editor/workflow`, `editor/llm-control/agent-packet` + `@/ui-kit/panel-frame/styles/panels.css`
- `block-outline.css` importují 4 soubory (BlockOutline, NodeTextEditor, NodeJournal, NodeLinksPanel)
- `shared/desktop-state/logic/*` importují ProjectMemoryPanel, NodeWorkflowPanel, AgentPacketPanel
- `shared/selection` importují ContextShelf, SourceExplorer, ProjectWorkspace, App
- `shared/surface-settings` importují Board, ModeRail, DrawingWorkspace, WorkspaceSettings, App

### 5.3 Dokumentace a skill
| Soubor | Změna |
|---|---|
| .claude/skills/opora-control-center/references/source-map.md:16–26 | 11 řádků cest |
| .claude/skills/opora-control-center/references/navigation.md:21 | ProjectLayout + project-layout.css |
| .claude/skills/opora-control-center/references/graphify.md:65 | GraphifyMap.tsx |
| docs/pravidla-struktury.md:7–30, 105–139 | cílový strom + „skutečný stav“ podle §2 |
| frontend/README.md | doplnit příběh z §0 |
| README.md v každé změněné složce | první věta = co složka zobrazuje a odkud bere data |

Zastaralý odkaz na `src/…` v backend/integrations/build_identity.py:10 je mimo rozsah; jen eviduji.

## 6. Ověření po fázi 2
1. `npm run build` (tsc --noEmit + vite build) – přiložit výstup
2. `git status --short` – jen R, M a A (nové README), žádné D
3. grep `frontend/shared/` a `frontend/ui-kit/` na importy `@/(app|layout|project-setup|project|editor|hub)` – musí být 0 výsledků
