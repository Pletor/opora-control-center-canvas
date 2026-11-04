# Plán: složka projektu jako jediné místo a procesy návrh → proces → hotovo → oprava

> Procesy (`/api/processes`, `backend/editor/process/`, `shared/process*.schema.json`) jsou odstraněné (rozhodnutí vlastníka 23. 10., audit sirotků B5); platí jen část o složce projektu.

Stav: všech 6 vrstev provedeno (2026-09-14); ověřeno v prohlížeči nad kopií produkčních dat: migrace při startu, záložka Proces, cyklus návrh → proces → oprava (z odpovědi agenta) → proces → hotovo, (přehled Procesy v Live Run byl později zrušen spolu s prostředím). Odchylky od plánu: `main/` a `workspaces` tabulka zůstávají v registru jako index; kresby, texty, zadání a deník zůstávají v `project.sqlite` (soubory `nodes/*.md` a `canvas/*.json` jsou další krok); `map-refresh/state.sqlite` zůstává napříč projekty, protože je to jedna fronta.

Schváleno 2026-09-14. Rozhodnutí uživatele: (1) klíčem je ID, frontend ukazuje název; (2) výstupy JSON a DB, Markdown podle typu procesu; (3) žádné duplicity, `main/` je čistý, každý nový pracovní prostor je git worktree.

## 1. Strom hlavní složky projektu `.data/production/projects/<project-id>/`

| Cesta | Co obsahuje | Odkud se sem stěhuje |
|---|---|---|
| `project.json` | ID, název, druh zdroje (git / local / empty), URL nebo cesta, větev, nastavení (cíl, platforma, revize) | tabulky `projects`, `project_sources`, `project_settings` |
| `main/` | čistá spravovaná kopie zdroje; nikdy se do ní nezapisuje | existuje |
| `worktrees/<wt-id>/` + `worktrees/<wt-id>.json` | git worktree pro běžící proces; metadata vedle složky | dnešní `workspaces/<wid>/` (přejmenování, tabulka `workspaces` → metadata JSON) |
| `canvas/graph.json` | graf plátna pro ne-git projekty (git pracovní prostory ho mají v `canvas/workspaces/<wid>/graph.json`; `main` jen čte verzovaný `opora-canvas.json` z Git HEAD) | tabulka `drafts` |
| `canvas/drawings/` | kresby po vrstvách | `drawing_revisions` (index v `project.sqlite`) |
| `nodes/<node-id>/text.md`, `spec.json`, `journal/<den>.md` | obsah uzlu, který čte agent | `node_text_revisions`, `node_spec_revisions`, `node_journal_revisions` (revize v `project.sqlite`) |
| `sectors/<sector-id>/` | totéž pro sektor (slot) | – |
| `processes/<prc-id>/process.json`, `reports/`, `result.md` | procesy a odpovědi agentů | nové |
| `memory/state.json` | pravidla, rozhodnutí, fáze uzlů | `desktop_v3_state` |
| `packets/<snap-id>.json` | neměnné snímky podkladů pro agenta | `desktop_v3_snapshots` |
| `maps/` | fronta obnovy map a běhy (`state.sqlite` per projekt) | `map-refresh/state.sqlite` (řádky daného projektu); artefakty zůstávají v `main/graphify-out` |
| `runs/` | složky běhů agentů | složky `llm-runs`, `coding-workspaces`, `task-handoff-*` (tabulky vazeb, aktivity a session byly zrušeny spolu s Live Runem) |
| `project.sqlite` | revize a indexy nad soubory výše (stejná schémata jako dnes, bez centrální DB) | – |

Mimo složku projektu zůstává jen `.data/production/registry.sqlite` (tabulky `projects` s cestou složky, `archived_projects`, `jobs`) a `claude-code-skills.json` (nastavení aplikace). Vestavěný projekt `draft` („Lokální návrh“) dostane vlastní složku `projects/draft/`.

Datový kořen (`.data/production`) smí ležet i mimo repozitář, aby se worktree vešly do limitu cest Windows: `uv run python tools/move_data_root.py <starý> <nový>` (backend zastavený) ho přesune, přepíše uložené absolutní cesty a zapíše `[app] data` do `opora.local.toml`. Složka worktree pracovního prostoru je `worktrees/<prvních 8 znaků wid>/`; celé ID zůstává v DB a ve větvi `work/<wid>`.

## 2. Kontrakt procesu

`shared/process.schema.json` a příklady `shared/examples/process-{draft,running,repair,done}.json`. Povinná pole: `id` (`prc-<12 hex>`), `projectId`, `nodeId` | `sectorId`, `title`, `state`, `createdAt`, `updatedAt`, `revision`, `owner` (human | agent | system), `inputs` (nodeText, spec, packet, worktree, references), `steps[]` (id `stp-<8 hex>`, state pending | running | done | failed, evidence), `outputs[]` (json | db | md | file + ref + digest), `failure` (reason, stepId, at, reportedBy, fix), `history[]` append-only.

## 3. Přechody stavů

| Z → do | Kdo | Podmínka |
|---|---|---|
| ∅ → draft | human, agent | založení; první záznam historie |
| draft → running | human, agent | `inputs.worktree` je id worktree, NEBO poznámka přechodu obsahuje „bez worktree“ (výslovné rozhodnutí) |
| running → done | human, agent | každý krok je `done` a má důkaz; žádný krok `failed` |
| running → repair | system, agent, human | `failure` s důvodem, krokem a autorem; krok dostane `failed`; nastane automaticky při reportu `step_failed`, timeoutu nebo neprůchozím testu |
| repair → running | human, agent | `failure.fix` vyplněný; `failed` kroky se vrátí na `pending`, důkaz zůstane v historii |
| done → repair | human | `failure` vyplněné (hotová věc se později ukázala rozbitá) |

Zakázané: draft → done, draft → repair, running → draft, done → running, done → draft, repair → done, repair → draft, jakýkoli přechod do téhož stavu. Každý zakázaný přechod má test.

## 4. Kanál odpovědi agenta

- Složka `processes/<prc-id>/reports/`, soubory `<UTC timestamp>-<agent>.json` podle `shared/process-report.schema.json`, append-only, nikdy se nepřepisují.
- Endpoint `POST /api/processes/{id}/reports`. Odpověď se uloží vždy, i když proces mezitím postoupil (pak dostane `stale: true`), takže agent nikdy neztratí kontext ani nepřeruší běh.
- Každá odpověď nese kontext: `processRevision`, `worktree`, `lastStepId`, `session`. Navazující agent čte `GET /api/processes/{id}` + poslední reporty a pokračuje.
- Promítnutí do `process.json`: `step_done` → krok `done` s důkazem (reportId); `step_failed` → krok `failed`, `failure` z `error`, přechod `running → repair` systémem; `progress` a `question` → jen historie reportů; `result` → výstupy procesu.

## 5. Worktree pravidlo

`main/` nikdy nedostane zápis. Proces ve stavu `running`, který mění kód, má `inputs.worktree` = `wt-<id>` vytvořený z HEAD `main/`. Fork cesty = nový worktree z HEAD jiného worktree. Ověření průchodnosti = příkaz spuštěný uvnitř worktree (`run_check`), výsledek jako důkaz kroku. Po `done` se worktree odstraní (větev může zůstat), pro `repair` zůstává vše.

## 6. Deduplikace

Registr odmítne druhý projekt se stejným zdrojem (URL nebo kanonická cesta, bez ohledu na velikost písmen). Dnešní dva záznamy „ample“: zůstane `aff4759e…` (má workspaces a nastavení), `7d1b72c6…` se při migraci sloučí (složka `main/` se smaže až po potvrzení).

## 7. Mapování na kód a pořadí vrstev

| Vrstva | Nové | Mění se | Test |
|---|---|---|---|
| 1 | `canvas/project_folder.py` (`ProjectFolder`: cesty uvnitř složky, `project.json`) | – | `test_project_folder.py` |
| 2 | `editor/process/process_store.py`, `process_lifecycle.py` | – | `test_process_store.py`, `test_process_lifecycle.py` (každý zakázaný přechod) |
| 3 | `editor/process/process_reports.py`, `api/editor/process_routes.py` | `app/factory.py` (include router) | `test_process_reports.py`, `test_process_routes.py` |
| 4 | `project/worktrees/worktree_manager.py` | – | `test_worktree_manager.py` (reálný git v tmp) |
| 5 | `canvas/migrate_to_project_folders.py` | `canvas_service.py` (`db_for(project)`, registr), `project_hub.py`, `node_text/specs/journal/drawings/removals`, `desktop_v3_state/packets`, `workspace_documents`, `map_refresh`, ; `DrawingStore`/`NodeSpecStore` dostanou service místo raw connection | všechny existující testy + `test_migrate_to_project_folders.py` |
| 6 | `frontend/editor/node-detail/process/` | `NodePanel.tsx` (záložka Proces) | build + kontrola v prohlížeči |

Pozorování z investigace, se kterými vrstva 5 počítá: 13 modulů volá `canvas.db`; `DrawingStore` a `NodeSpecStore` dostávají raw spojení; `agent_bindings.bound_run_keys(source_id)` a `map_refresh.claim()` jsou dnes napříč projekty (registr si ponechá souhrnný index); `workspace_documents.save` zapisuje do `project_settings` v jedné transakci (obě tabulky zůstanou v `project.sqlite`); test `test_project_hub.py:84` počítá s legacy `canvas.sqlite` (migrační skript ho převede).

## 8. Frontend

Detail uzlu dostane záložku **Proces** (stav, kroky, důkazy, poslední odpovědi agentů, tlačítka přechodů podle tabulky). Všude se ukazuje název projektu a název procesu, ID jen v detailu a v API.

## 9. Ověření
`uv run pytest` bez nových selhání oproti baseline (2 graphify selhání jsou známá); proces projde všemi čtyřmi stavy přes API; `step_failed` přepne do repair bez ztráty historie; report do běžícího procesu je vidět s kontextem; frontend zobrazuje názvy.
