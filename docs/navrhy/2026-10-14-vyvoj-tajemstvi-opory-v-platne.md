# Vývoj Tajemství opory v plátně OPORA — fáze 1 (analýza a návrh)

Stav k 2026-10-14. Jen čtení, nic se neregistrovalo ani nezapsalo. Plátno :8740 v době analýzy neběželo (`curl /api/map-refresh/config` bez odpovědi). Zkratky: **TO** = `P:\…\Tajemstvi-opory`, **PL** = toto repo.

## 1. Ověření tvrzení

| Tvrzení | Verdikt | Doklad |
|---|---|---|
| pipeline/ mimo git, approve SHA-256 | platí | TO `.gitignore:117`; `pipeline/approve.ps1:12` volá `guard.py approve`, otisky `guard.py:481,506` |
| 7 trailerů, verify-commit | platí | TO `pipeline/work/_common.py:47-58`, `guard.py:648-680,709` |
| max 2 kola, pak eskalace | platí | TO `docs/agent-system/delegation.md:48,83` |
| kritik z jiné rodiny | platí | TO `delegation.md:16` |
| vodopád obcházen od 2026-09-02 | platí, ale **ne jen od 2. 9.** | všech 17 běhů od `2026-09-02-*` nemá `01-goal.md`; bez něj jsou i `2026-08-21-brain-process`, `2026-08-28-atomic-user-erasure` |
| ruční workunit.json a export PRUBEH | částečně | `workunit.json` nemá generátor (žádný zápis v `hermes_work.py`); PRUBEH se připisuje automaticky (`hermes_work.py:395-419`), do PRD jde ručně přes `prubeh --export` (`:469,1784`) |
| odkazy na Bridge :8710 / OporaCC | platí | `docs/opora-workflow/00-PLAN.md:49` míří na `../02.Opora-control-center/opora-supervisor-bridge/`, který neexistuje; na 8710 nic neposlouchá. **Navíc:** `docs/opora-workflow/` je v TO nesledovaný (`??`) |
| nejednotná brána | platí | `package.json:28` `be2:check` vs `mise.toml:210-228`; SPECy uzlů volají `be2:check` (např. `canonical_bytes/SPEC.md:34`) |
| úkoly na ~8 místech | platí | A-x, `work/R-x`, `docs/opora-workflow/uzly/*/TODO.md` (10× T-x), `01-ROZHODNUTI.md` (29 řádků s R-xx), `tasks/*.task.md`, `.claude/workbench/`, `pipeline/projects/`, vault |
| Tajemství opory není v plátně | platí | `.data/production/projects/*/project.json`: 6 projektů + draft, žádný TO |
| GitHub vertikála „planned" | **neplatí celé** | štítek `frontend/settings/logic/connectors.ts:22` ano, ale backend umí klon (`backend/canvas/canvas_service.py:782`), ff-sync (`:801`), worktree (`:720`) a záznam `prUrl` (`backend/canvas/source_realization.py:10-20`). Chybí push, PR a čtení stavu merge |
| graf = SQLite + `opora-canvas.json` ve worktree | **jen pro git projekt** | lokální/prázdný projekt drží graf v `project.sqlite` (`canvas_service.py:709`); soubor jen pro git (`:714`) |
| registr `registry.sqlite` | upřesnění | živý registr je `CanvasService.db` se schématem `database/schema/project_schema.py:8-11`; třída `backend/canvas/project_registry.py:27` se nikde neinstancuje (mrtvý kód) |
| lease nepovinný | platí | `card_leases.py:24-35` blokuje jen při cizím platném lease; bez claimu zápis projde |
| task_execution prázdný | platí | jen `backend/editor/task_execution/README.md:1` |
| MCP neexistuje | platí | `connectors.ts:24` planned, v backendu žádný MCP server |
| App.tsx 1797 řádků | platí | cesta `frontend/app/components/App.tsx` |
| MAX_RETRIES=2, kritici user/sly/hacker, done jen člověk | platí | `card_pipeline.py:22-24,42`; `backend/app/human_session.py:22` |
| trailery karty a evidence checků chybí | **neplatí** | trailer `Opora-Node` (`backend/canvas/commit_pairs.py:14`), `POST /api/check-run` (`backend/api/editor/sync_routes.py:22`, `backend/canvas/check_runs.py`) |

## 2. Mapování procesu

| Prvek TO | Protějšek v PL | Stav | Doporučení — důvod |
|---|---|---|---|
| Plán GOAL→DETAIL, A-x v `01-goal.md` | sektor + karty (`/api/canvas-plan`), `goal`/`definitionOfDone`, schránka zadání `/api/brief-vault` | existuje | **přizpůsobit**: A-x = `node.checks` sektoru, protože vodopád se od září stejně nepoužívá |
| Schválení SHA-256 stupňů | brána sektoru člověkem, `assignment-snapshot` | existuje | **přizpůsobit**: snímek zadání nahradí otisk schváleného stupně |
| PRD.md + SPEC.md uzlu | `/api/node-spec`, `sourceRef` karty | částečně | **převzít beze změny v repu**, karta jen odkazuje — kód a testy je čtou |
| `tasks/*.task.md`, `workunit.json` | karta + `node-brief` (`boundaries`, `outputContract`) | existuje | **zahodit soubory**: allowed_paths/tier patří do karty, ruční JSON odpadne |
| HANDOFF.md | `stages[].note`, `reports` na vazbách, `agent-workspace` | existuje | **zahodit** — předávka žije na kartě |
| Writer Hermes (`hermes_work.py`) | lease → brief → `agent-output`; `task_execution/` slot | chybí vykonavač | **přizpůsobit**: Hermes jako externí agent smyčky (`agent-loop.md`) |
| 7 trailerů + verify-commit | `Opora-Node` + párování commitů | konflikt | **přizpůsobit**: `Node`/`Run` → ID karty a revize briefu; verify-commit zůstává jako CI check |
| `mise run check` / `check-full` | `node.checks`, `checksRun`, `/api/check-run` | existuje | **převzít**: příkaz je check karty, výsledek jde do `/api/check-run` |
| CI `.github/workflows/ci.yml` | nic (jen ruční zápis běhu) | chybí | **převzít**; výsledek CI se má do plátna dostat (bod 5.3) |
| Kritik jiné rodiny, 3 kritici UI | etapy `critic` user/sly/hacker, nezávislost jménem relace | částečně | **přizpůsobit**: plátno hlídá autora, ne rodinu modelu |
| Max 2 kola → ESCALATED | `MAX_RETRIES=2`, pak člověk | existuje | **převzít** — sémantika shodná |
| PR, merge člověkem | `realize-source` (`commit`, `prUrl`), `done.confirmed` jen člověk | částečně | **převzít**; chybí čtení stavu PR |
| Vault 10-RAW zrcadlo | Graphify/Archify mapy, `docs` karty | konflikt | **ponechat mimo plátno** zatím; NEOVĚŘENO, zda mapy RAW nahradí |
| Dohled (`mise run dohled`, agenttrail :5330, `mise.toml:63-70`) | `work-overview`, `trace`, záznam činnosti | existuje | **zahodit agenttrail** po přechodu; plátno vidí karty i lease |
| `00-PLAN.md`, `uzly/*/TODO.md`, `01-ROZHODNUTI.md` | sektory, `/api/desktop-v3/decision` | existuje | **zahodit** po migraci; rozhodnutí → decision |

## 3. Registrace projektu — dvě existující cesty, žádná nespojí složku i remote

**A) Lokální složka** — `POST /api/local-project` `{"name","path","confirmed":true}` (`backend/api/project_setup/project_routes.py:17`, `backend/project_setup/project_hub.py:150-170`).
- Zapíše jen do `.data/production`: řádky `projects` + `project_sources` (kind `local`), složku `projects/<uuid>/` s `project.json` a podsložkami (`backend/canvas/project_folder.py:93-111`), graf jako draft v `project.sqlite`.
- Do TO **nezapíše** `opora-canvas.json`, worktree **nevytvoří** (`canvas_service.py:732` git workspace odmítne); pracovní prostor je jen `draft`.
- **Riziko:** automatika map (výchozí zapnutá, `backend/project/maps/map_refresh.py:52,105-114`) uvidí `.git` a `refs/heads/main` v TO a zařadí první běh. Ten zapíše `graphify-out/` (v TO ignorovaný, `.gitignore:100`, ale přepíše současný graf) a `archify-out/` do pracovní kopie, přidá řádek do `.git/info/exclude` (`map_git_exclude.py:12-13`) a spustí Claude Sonnet pro Archify (`docs/mapy-projektu.md:17,25`). **Před registrací vypnout** `POST /api/map-refresh/configure {"enabled":false}` (globálně), po ní `POST /api/map-refresh/settings {project,tool,automatic:false}`.
- GitHub URL k lokálnímu projektu připojit nelze (payload je přesně tři klíče, `project_hub.py:152`).

**B) GitHub remote** — `POST /api/connect` `{"url":"https://github.com/Pletor/Tajemstvi-opory","approved":true}` (`canvas_service.py:782-799`).
- Úloha na pozadí naklonuje repo do `.data/production/projects/<uuid>/main` (vlastní kopie, TO nedotčen), název = `Tajemstvi-opory`, kind `git`, `main` jen ke čtení. Stav úlohy v bootstrapu (`jobs`).
- Repo je **PRIVATE** (`gh repo view`); klon jede s `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never` (`backend/integrations/gitio.py:19`) — uspěje jen s uloženými přihlašovacími údaji. NEOVĚŘENO.
- Práce: `POST /api/workspaces {project,nodeId,actor}` → `git worktree add` větev `work/<uuid>` v `projects/<uuid>/worktrees/` (`canvas_service.py:720-746`). Graf plátna = `opora-canvas.json` **v kořeni worktree** (`:714`), tedy na pracovní větvi TO — při `git add -A` skončí v PR. Push neexistuje; aktualizace `POST /api/sync {project,confirmed:true}` jen ff-only (`:801-822`).

A a B mohou běžet vedle sebe jako **dva projekty** (kontrola duplicit jen u lokální cesty, `project_hub.py:163-170`).

## 4. Cílový proces „vše v plátně"

1. **Podnět** → schránka zadání (`brief-vault create/split/propose-mvp`) nebo přímo karta.
2. **Plán** → sektor = řez (dříve běh), karty = R-x/T-x; `checks` = A-x; brána sektoru schvaluje člověk.
3. **Specifikace** → Fable napíše `PRD.md`/`SPEC.md` do worktree karty; karta je odkazuje (`sourceRef`).
4. **Práce** → writer: `frontier` → `lease claim` (povinně) → `node-brief` → kód v worktree → commit s `Opora-Node` + otisky → `agent-output` s `checksRun`.
5. **Kontrola** → etapy `test` (`mise run check`), `review`, `critic` ×3, max 2 opravy, pak člověk.
6. **PR a merge** → agent otevře PR (dnes ručně `gh`), člověk merguje, `realize-source` zapíše SHA a `prUrl`, člověk potvrdí `done`.

**Zrušit v TO:** `pipeline/runs/*/01-…04-*.md` pro nové řezy, `tasks/*.task.md`, `HANDOFF.md`, ruční `workunit.json`, `docs/opora-workflow/` (00-PLAN, TODO, ROZHODNUTI), `.claude/workbench`, agenttrail dohled. **Zůstává v TO:** `PRD.md`/`SPEC.md` uzlů, trailery a `guard.py verify-commit` (přepojené na kartu), `mise run check(-full)`, CI, chráněný `main`, vault RAW (do rozhodnutí).

## 5. Vylepšení plátna (priorita shora)

| # | Problém | Moduly | Vel. | Riziko |
|---|---|---|---|---|
| 1 | Registrace přes `local-project` sahá mapami do cizí pracovní kopie | `backend/project/maps/map_refresh.py`, `map_artifacts.py`, `project_hub.py` | S | nízké |
| 2 | Lease není povinný, dva agenti můžou psát na kartu | `backend/editor/agent_memory/card_leases.py:24-35`, `agent_output.py` | S | střední (rozbije stávající skripty bez claimu) |
| 3 | Výsledek `mise run check` a CI se do plátna nedostane sám | `backend/canvas/check_runs.py`, skill `opora_closure.py`, nový krok v CI TO | M | nízké |
| 4 | Chybí PR vertikála: push, otevření PR, čtení stavu merge | `backend/integrations/gitio.py`, `source_realization.py`, `connectors.ts:22` | L | vysoké (tokeny, nevratné operace) |
| 5 | `opora-canvas.json` se commituje do cílového repa | `backend/canvas/canvas_service.py:714` | M | střední (migrace grafu) |
| 6 | Trailery TO a `Opora-Node` se neznají | `backend/canvas/commit_pairs.py:14`, `sync_report.py` | S | nízké |
| 7 | Prázdný slot vykonavače pro writera (Hermes/opus) | `backend/editor/task_execution/` | L | vysoké (spouštění modelů mimo tři povolená místa, `CLAUDE.md`) |
| 8 | Agenti mimo okno jen přes skripty, ne MCP | nový modul, `connectors.ts:24` | M | střední |
| 9 | Kritik hlídá jméno relace, ne rodinu modelu | `card_pipeline.py:34` (`INDEPENDENT`) | S | nízké |
| 10 | Mrtvý `ProjectRegistry` mate čtenáře | `backend/canvas/project_registry.py` | S | nízké |


## 6. Otevřené otázky pro člověka

1. Registrovat TO jako **lokální** (vaše pracovní kopie, bez worktree), **git klon** (oddělená kopie, worktree, ale `opora-canvas.json` v repu), nebo obojí?
2. Smí plátno mít přístup k privátnímu repu (uložené přihlašovací údaje / token pro `gh`)?
3. Mají se mapy (Graphify/Archify, Sonnet) nad TO spouštět automaticky, nebo vypnout? Smí přepsat současný `graphify-out/`?
4. Smí graf plátna (`opora-canvas.json`) být v repu TO a v PR, nebo musí zůstat mimo git?
5. Kdo je writer v plátně: Hermes přes `hermes_work.py` jako externí agent, nebo subagent opus — a smí plátno model spouštět samo (`task_execution`)?
6. Zůstávají 7 trailerů + `verify-commit` povinné, a co nahradí `Run`/`WorkUnit-SHA256`?
7. Jaký osud mají rozpracované běhy v `pipeline/runs/` a `docs/opora-workflow/` (migrace do karet, archiv, nic)?
8. Je vault 10-RAW dál povinný „řez = kód + zrcadlo", nebo ho nahradí mapy plátna?
9. Která brána je kanonická: `mise run check` nebo `npm run be2:check`?
10. Smí agent push a otevřít PR, nebo i to zůstává člověku?
