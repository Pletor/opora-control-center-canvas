# Architektura Opora Control Center Canvas — specifikace diagramu (archify)

Datum: 2026-09-11. Revize repa: `930620ca9015dd49650548b63922b79e8ab92186` (větev `main`).
Zdroj pravdy: skutečný kód, konfigurace a dokumentace repa. Ruční graf OPORY ani `.opora/` běhové artefakty
nebyly použity jako důkaz.

## Výstupy

| Soubor | Účel |
|---|---|
| `opora-canvas.architecture.json` | Archify spec (schema_version 1, typ `architecture`, profil `showcase`) |
| `opora-canvas.architecture.html` | Doručené interaktivní HTML (inline SVG, světlé/tmavé téma, export) |
| `opora-canvas.evidence.json` | Důkazy soubor:řádek pro každý modul (mimo spec, viz Omezení) |
| `validate-receipt.json`, `deliver-receipt.json` | Receipty validace a doručení (SHA-256, byty) |
| `visual-check-receipt.json` + `*.visual-check.*.png/.html` | Automatická kontrola v Chrome ve 4 viewportech × 2 témata |

## Identita projektu

`opora-control-center-canvas` 0.1.0 (`package.json:2-3`, `pyproject.toml:2-3`). Canvas nad schváleným Git
repozitářem: projekt → sektor → uzel, čistý `main` oddělený od pracovních worktrees (`PRODUCT-CONTRACT.md:13,25-37`).
Stack: React 19 + TypeScript + `@xyflow/react` + Excalidraw, Vite (`package.json:11-25`); Python ≥ 3.11 + FastAPI +
uvicorn (`pyproject.toml:4-9`), SQLite a Git CLI (`README.md:41`).

## Moduly (12) a hranice (4)

| id | Hranice | Typ | Role | Důkaz |
|---|---|---|---|---|
| fe-shell | Frontend | frontend | Kořen SPA, módy Struktura/Kreslení/Mapa, React Flow plátno | `src/App.tsx:1`, `src/Board.tsx:4`, `src/main.tsx:9` |
| fe-drawing | Frontend | frontend | Lazy-loaded Excalidraw, kresba per vrstva | `src/DrawingWorkspace.tsx:163`, `src/App.tsx:26` |
| fe-panels | Frontend | frontend | Desktop v3 panely (paměť projektu, workflow, agent packet, live workspace) | `src/desktop-v3/index.ts:1`, `src/desktop-v3/api.ts:41`, `src/desktop-v3/live-sessions.ts:37` |
| be-app | Backend API | security | `create_app()`, host/origin/JSON gate, inline routes, mount `dist/` | `backend/app.py:29`, `:63-91`, `:289-291` |
| be-service | Backend API | backend | CanvasService: graf, projekty, workspaces, Git operace, souborový strom | `backend/service.py:27`, `:376`, `backend/workspace_sources.py:223` |
| be-context | Backend API | backend | Kontextové pakety (`opora.packet/1`), Desktop v3 packet routes | `backend/context_packets.py:1`, `backend/desktop_v3_packets.py:1`, `backend/desktop_v3_routes.py:8` |
| be-runs | Backend API | backend | LLM běhy, coding běhy, dokumentační handoffy a workery | `backend/llm_runs.py:1`, `backend/coding_runs.py:1`, `backend/task_handoff_routes.py:7` |
| be-observability | Backend API | backend | Zdroje agentů, vazby na uzly, sessions Hermes/Claude | `backend/agent_routes.py:42`, `backend/node_sessions.py:313` |
| store-sqlite | Úložiště | database | `canvas.sqlite`, jediná DB | `backend/service.py:35,40`, `backend/llm_runs.py:192`, `backend/desktop_v3_state.py:192` |
| store-fs | Úložiště | database | Datový adresář `projects/<id>/main`, `workspaces/<wid>` | `backend/service.py:374,425`, `backend/task_handoffs.py:26-27` |
| ext-git | Externí | external | Git CLI (clone, worktree, sync) | `backend/gitio.py:17-40`, `backend/service.py:376` |
| ext-docker | Externí | external | Docker, pinned image, `--pull=never` | `backend/coding_tools.py:48-49`, `backend/coding_runs.py:212` |
| ext-hermes | Externí | external | Hermes CLI (`hermes chat --safe-mode`) a API 127.0.0.1:8642 | `backend/llm_runs.py:215`, `backend/node_session_sources.py:24` |
| ext-oporacc | Externí | external | OporaCC/Plátno HTTP 127.0.0.1:8738 | `backend/agent_sources.py:96,217` |

## Vztahy v diagramu (14) a jejich důkazy

| Vazba | Popisek | Důkaz |
|---|---|---|
| fe-shell → be-app | HTTP /api/bootstrap, /view, /graph, /connect, /sync | `src/App.tsx:175,186,246,875,484` ↔ `backend/app.py:120,140,159,267,277` |
| fe-drawing → be-app | HTTP /api/drawing | `src/DrawingWorkspace.tsx:163,256` ↔ `backend/app.py:144,148` |
| fe-panels → be-app | HTTP /api/desktop-v3, /task-handoffs, /llm/runs, /node-sessions | `src/desktop-v3/api.ts:41,126`, `live-sessions.ts:37`, `node-sessions.ts:68` ↔ `desktop_v3_routes.py:8`, `task_handoff_routes.py:7`, `app.py:255`, `node_sessions.py:313` |
| be-app → be-service | instanciuje | `backend/app.py:10-26,30-44` |
| be-app → be-context / be-runs / be-observability | include_router | `backend/app.py:10-26,30-44` |
| be-service → store-sqlite | sqlite3 | `backend/service.py:35,40` |
| be-service → store-fs | checkout a worktrees | `backend/service.py:374,425` |
| be-service → ext-git | git clone/worktree | `backend/service.py:376`, `backend/gitio.py:17-40` |
| be-runs → ext-docker | docker run --rm | `backend/coding_tools.py:48-49,70`, `backend/coding_runs.py:212` |
| be-runs → ext-hermes | hermes chat --safe-mode | `backend/llm_runs.py:215,411-424` |
| be-observability → ext-hermes | HTTP sessions 8642 | `backend/node_session_sources.py:24,161` |
| be-observability → ext-oporacc | HTTP status 8738 | `backend/agent_sources.py:96,217` |

Doložené, ale z diagramu vynechané kvůli čitelnosti (křížení koridorů):
- be-runs → store-sqlite: tabulky běhů v téže DB (`backend/llm_runs.py:192`, `backend/desktop_v3_state.py:192`).
- be-app → frontend build: mount `dist/` jako StaticFiles (`backend/app.py:289-291`); Vite dev proxy `/api` → 8740 (`vite.config.ts:5`).
- be-observability → VS Code: `Popen(Code.exe)` pro otevření souboru (`backend/workspace_sources.py:167-179`).
- Testy → be-app: `uvicorn backend.app:create_app` v e2e lane (`playwright.config.ts:9`); 56 pytest souborů, 17 Playwright konfigurací, 7 e2e adresářů.

## Porty z konfigurace

| Port | Proces | Důkaz |
|---|---|---|
| 8740 | produkce uvicorn (`OPORA_CANVAS_PORT`) | `README.md:34`, `backend/app.py:59` |
| Vite dev | `vite --host 127.0.0.1`, proxy `/api` → 8740 | `package.json:7`, `vite.config.ts:5` |
| 8742, 8762, 8764, 8766, 8769, 8771 | e2e lane uvicorn | `playwright.*.config.ts` |
| 8782 | Vite harness Desktop v3 (a uvicorn node-live) | `vite.desktop-v3.config.ts:10`, `playwright.node-live.config.ts:6` |
| 8783, 8793–8796 | fixture / export / workflow / inspector / keyboard lane | příslušné `playwright.*.config.ts` |
| 8642, 8738 | externí klienti (Hermes API, OporaCC) | `backend/node_session_sources.py:24`, `backend/agent_sources.py:96` |

## Validace

- `validate architecture --quality showcase`: ok, 0 diagnostik (9 artefaktových kontrol, 0 chyb kompozice, 0 varování).
- `deliver`: ok; spec SHA-256 `93efd05c6cbc6d6b445e2bbaff70fc26c9243e68c950959a1eab9f49b05d3d9c` (9 460 B),
  HTML SHA-256 `0f751326541046b34242602a8378e8663758256a3a4058b2b1ba58c0101b9302` (726 388 B).
- `visual-check`: pass; containment, readability a viewer chrome pass ve 1440×900, 1600×1000, 1920×1080, 2048×1320
  (světlé i tmavé téma), bez horizontálního i vertikálního přetečení; minimální projekce textu 6,27 px při 1440×900.
- Perceptuální kontrola: snímek 1440×900 (světlé téma) prohlédnut autorem, viz závěr v hlášení.

## Omezení analýzy

- Nečteno: `node_modules/`, `.venv/`, `uv.lock`, obsah `package-lock.json`, `dist/`, `.data/`, `test-results/`,
  `evidence/*.png`, `.env*`, `*.tsbuildinfo`. `.opora/` a `.worktrees/` jen vyjmenovány.
- Těla některých backend modulů (`agent_catalog`, `agent_bindings`, `removals`, `project_hub`, `drawings`, `graph`,
  `planning_context`) nebyla čtena; role odvozena z importů v `app.py`/`service.py` a docstringů.
- Repo nemá GitHub remote, proto archify nemohl strojově ověřit `sources` (vyžaduje `meta.repository` s veřejnou
  URL). Důkazy jsou v `opora-canvas.evidence.json` a v této specifikaci.
- Nesrovnalosti: `README.md:24` uvádí Playwright port 8741, žádná konfigurace ho nepoužívá; 8782 a 8793 sdílí dvě
  konfigurace; `backend/agent_routes.py:25` obsahuje absolutní cestu konkrétního uživatele.
- Runtime dostupnost Hermes, OporaCC a Docker nebyla ověřena (kód má fallback „unavailable“).
- Viewer UI a `<html lang>` archify jsou anglicky (renderer nepřekládá; `meta.locale` pro češtinu neexistuje).
- Zdrojový kód aplikace nebyl měněn; přibyla jen složka `docs/architecture/archify/`.
