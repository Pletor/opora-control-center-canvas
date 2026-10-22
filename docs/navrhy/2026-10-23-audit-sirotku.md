# Audit sirotků, nepoužívaných a nefunkčních částí OPORA Canvas

Stav k 2026-10-23, větev `docs/audit-sirotku` z `origin/main` (`a6a28b0`). Jen čtení: živá aplikace
`http://127.0.0.1:8740` jen GET, SQLite jen `mode=ro`. Každý verdikt má důkaz; kde důkaz nestačí,
stojí **OVĚŘIT** s tím, co ověřit.

Verdikty: **ODSTRANIT**, **NAHRADIT** (čím), **PONECHAT** (proč), **OVĚŘIT** (co).

## Zdroje důkazů

| Zdroj | Příkaz / místo | Výsledek |
|---|---|---|
| Mrtvý kód Python | `uvx vulture backend database library --min-confidence 80` / `60` | 10 / 160 nálezů; po třídění 10 skutečných (B9) |
| Mrtvý kód TS | `npx knip@5` (vstup `frontend/app/components/main.tsx`, s testy i `--production`) | 7 nepoužitých souborů, 4 další jen pro testy, 99 exportů, 166 typů, 1 devDependency |
| Routy | `GET /openapi.json` živé aplikace → 284 rout; hledání volajících ve `frontend/`, `shared/`, skill `opora-control-center`, `tools/`, `agent-office/src` | 37 bez přímého volajícího; po ruční kontrole (URL skládané z proměnných) 19 skutečně bez volajícího |
| Data | 12 × `P:/opora-data/projects/*/project.sqlite`, `registry.sqlite`, `agent-control/hooks.sqlite`, `map-refresh/state.sqlite` | tabulky a počty níže |
| Aktivita | `registry.activity_log` (9 150 řádků, 2026-10-06 → 2026-10-22, jen zápisy POST/PATCH) | 8 264 agent, 581 člověk, 305 unknown |
| Historie | `git log -S` u každého sirotka | kdy a kterým PR ztratil rodiče |
| Testy | dva známé pády, spuštěné samostatně (bez a s `OPORA_GRAPHIFY_PYTHON`) | kořenová příčina v §5.1 |

## Souhrnná tabulka

| # | Položka | Druh | Důkaz (zkráceně) | Verdikt | Navržené PR |
|---|---|---|---|---|---|
| 1 | Agent hooks (`/api/agent-hooks/*`, `backend/agent_control/`, `vscode_installer.py`, `tools/opora_hook.py`) | backend bez UI | UI smazáno v `eafc410` (2026-10-14); `hooks.sqlite`: 0 vazeb, 0 událostí; `bind/control/events/vscode` bez volajícího | ODSTRANIT | B3 |
| 2 | Starší procesy `/api/processes/*` (6 rout) | backend bez volajícího | 1 soubor `process.json` z 2026-09-14; žádný volající nikdy ve FE; docs tvrdí „UI + agent, hotovo“ | ODSTRANIT routy, ProcessStore OVĚŘIT | B5 |
| 3 | Balíček pro agenta `packet/preview`, `packet/snapshot`, `external-export` | backend + FE API bez UI | UI smazáno v `7465a5a` (2026-10-15); poslední snímek 2026-09-11 (4 řádky, 1 projekt); `api.ts` funkce nevolané (knip) | ODSTRANIT | B4 |
| 4 | `/api/desktop-v3/confirm-proposals` (hromadné potvrzení sektoru) | regrese UI | člověk volal 37× (naposledy 2026-10-15); tlačítko smazáno v `b9e761c` (#30) | OVĚŘIT → NAHRADIT nebo ODSTRANIT | – |
| 5 | `SpecificationDiff` + `/assignment-comparison` | sirotek po souběžných PR | zobrazení smazáno v #30, logiku #36 téhož dne upravil; komponenta jen v testu | OVĚŘIT | – |
| 6 | Hromadné posouzení pravidel (`rule-batch.ts`, `reviewRules`, `/rule-review-batch`) | hotová logika bez UI | `bd16f73` přidal backend + logiku bez komponenty; 214 čekajících návrhů pravidel agentů ve 4 prostorech | NAHRADIT: dodělat UI v Paměti projektu | – |
| 7 | `node-brief.boundaries.proposedRules` | šum pro agenty | 115/115 návrhů patří jiným kartám; 25,6 kB × 2 (kopie v `orientation`) = 51 % ze 100 kB briefu | NAHRADIT: filtr podle rozsahu, bez duplicity | – |
| 8 | `NodeTree.tsx`, `TreeBlock.tsx` + nenačtený `tree.css` | sirotek + vizuální chyba | rodič zrušen v `7465a5a`; `tree.css` importuje jen `NodeTree`, nasazené CSS nemá `.tree-part/.tree-todos/.tree-status-chip`, které používá živý `BlockEditor` | ODSTRANIT + přesunout import CSS | B1 |
| 9 | `NodeLibraryDrawer.tsx`, `LibraryContext.tsx`, `library-model.ts(+test)` | sirotek | sekce Knihovna smazána v `eafc410`; `node-library.css` dál používá `BlockEditorDrawer` | ODSTRANIT (CSS ponechat) | B1 |
| 10 | `CardReviewGate.tsx` | sirotek | nahrazeno záložkou Review v šuplíku karty (#28 `928fced`); logika `gate-view.ts` žije dál | ODSTRANIT | B1 |
| 11 | `use-decision-rounds.ts` + `GET /card-rounds` | sirotek | volání zrušeno v #28; `card_rounds` 0 řádků ve všech DB | ODSTRANIT hook, kola OVĚŘIT | B1 |
| 12 | `evidence-readiness.ts(+test)` | jen test | poslední použití zrušeno v #30 | ODSTRANIT | B1 |
| 13 | `rule-batch.ts` (bez UI) | nepoužitý soubor | viz #6 | podle #6 | – |
| 14 | `/api/desktop-v3/tags`, `/api/node-spec/history` | routy bez volajícího | `git log -S` ve FE: nikdy volány; skill ani office je nezná | ODSTRANIT | B2 |
| 15 | `/api/check-run` (GET/POST) + `check_runs` | backend bez volajícího | 0 řádků ve všech DB; volá ho jen dokument; agenti hlásí `checksRun` v `agent-output` | OVĚŘIT (sync-report ho čte) | – |
| 16 | `/api/opora-merge` | backend bez volajícího | `opora_commits` 22 řádků (1 projekt, 1 karta), žádný merge | OVĚŘIT | – |
| 17 | Zrcadlo (`/brief-vault/mirror`, `[mirror]`) | nefunkční model č. 4 | sidecar `127.0.0.1:8750` odmítá spojení, `health: null`; poslední událost 2026-10-15; průměrná přesnost 0,31 (17 oborů); FE route nevolá | OVĚŘIT → vypnout nebo ODSTRANIT | – |
| 18 | Automatická aktualizace map (Archify Sonnet + Graphify) | nefunkční model č. 1 | všech 5 zapsaných projektů `failed`: „Snapshot vyžaduje 1–800 souborů a 8 MiB“; Opora má 2 412 textových souborů | NAHRADIT: snapshot podle `.graphifyignore` a mezí Graphify | B7 |
| 19 | Dva padající testy Graphify | nefunkční testy | §5.1 | NAHRADIT (oprava testů) | B6 |
| 20 | OporaHub v2 (64 tabulek `opora_*` mimo `opora_events` a `opora_commits`) | nezavedeno | UI 29 dílků, office napojen; 0 přijatých revizí zadání → office execution nesmí startovat; 0 lidských zápisů do `/api/oporahub/*` | PONECHAT, rozhodnutí vlastníka | – |
| 21 | Dotazování review slotů `/review-jobs/claim` | šum | 3 668 claimů za 7 h (2026-10-22 13:44–20:34), 0 úloh kdy; 40 % celého `activity_log` | NAHRADIT: backoff/stream, nelogovat prázdný claim | – |
| 22 | Mrtvé tabulky `node_sessions`, `agent_bindings`, `agent_binding_scopes`, `agent_activity_entries` | data | v kódu 0 odkazů, všude 0 řádků, jen ve 3 starých DB | ODSTRANIT migrací | B8 |
| 23 | Mrtvé symboly Pythonu (10) | kód | vulture 60 % + grep: 0 použití | ODSTRANIT | B9 |
| 24 | `prettier` v `devDependencies` | závislost | knip; žádný skript ani konfigurace | ODSTRANIT | B2 |
| 25 | `opora_read.py node-brief` čte `harness.phase` | agentí nástroj | producent `node_brief.py:405` pole `phase` nikdy nevydá → vždy `null` | NAHRADIT (číst `pipeline.current`) | – |
| 26 | Dokumentace popisující neexistující kód | docs | `workflow-opora.md:34–35` („hotovo“ u Procesů a Hooků); `panely-editoru.md:55,65`, `rozvrzeni-editoru.md:95,103` (`layout/library-navbar`, `agent-navbar`); `tools/doc_check.py`: 277 mrtvých odkazů | NAHRADIT ve stejných PR | B3, B5 |
| 27 | FE fixtures (8 souborů `*fixtures.ts`, `lens-fixture.ts`) | jen testy | knip `--production` | PONECHAT (testovací data) | – |
| 28 | `node-crypto-shim.ts` | „nepoužitý“ | připojen aliasem ve `vite.config.ts` | PONECHAT | – |
| 29 | ~130 handlerů rout ve vulture, 99 exportů / 166 typů v knip | falešné nálezy | FastAPI dekorátory; konstanty exportované pro testy | PONECHAT | – |

## 1. Backend

**Routy bez volajícího (po ruční kontrole).** Z 37 kandidátů měla většina volajícího přes skládané URL
(`${base}/…`, `ROOT + '/claim'`): asistent (`assistant-api.ts`), observer (`isolated-observer.ts`),
budgets/policy history (`use-execution-budgets.ts:29`, `use-review-policy.ts:41`), receipts
(`ProposalReview.tsx:62`), reconciliation candidate, `/scenario-history` a `/assignment-status`
(`opora_read.py`). Skutečně bez volajícího zůstalo:

| Routa | Poslední volající (git) | Data | Verdikt |
|---|---|---|---|
| `POST /api/agent-hooks/bind`, `/control`, `GET /events`, `GET/POST /vscode` | `HookSection.tsx` atd., smazáno `eafc410` | `hooks.sqlite` 0/0, `agent-control/clients/` prázdné | ODSTRANIT celé (B3) |
| `POST /api/agent-hooks/event`, `/ack` | jen `tools/opora_hook.py` — bez vazby nemá klienta | 0 | ODSTRANIT (B3) |
| `/api/processes*` (6) | nikdy ve FE pod touto cestou | 1 soubor z 2026-09-14 | ODSTRANIT (B5) |
| `POST /packet/preview`, `/packet/snapshot`, `GET/POST …/external-export` | `7465a5a` | 4 snímky, poslední 2026-09-11 | ODSTRANIT (B4) |
| `GET /packet/snapshots/{id}` | `opora_read.py:511` | bez nových snímků | ODSTRANIT s B4 |
| `POST /api/desktop-v3/confirm-proposals` | `b9e761c` (#30) | 37 lidských volání do 2026-10-15 | OVĚŘIT |
| `GET /api/desktop-v3/assignment-comparison` | `b9e761c` (#30) | – | OVĚŘIT |
| `GET /api/desktop-v3/card-rounds` | `928fced` (#28) | `card_rounds` 0 | OVĚŘIT |
| `GET /api/desktop-v3/tags`, `GET /api/node-spec/history` | nikdy | – | ODSTRANIT (B2) |
| `GET/POST /api/check-run` | nikdy | `check_runs` 0 | OVĚŘIT |
| `POST /api/opora-merge` | nikdy | 22 commitů, 0 merge | OVĚŘIT |
| `GET /api/brief-vault/mirror` | nikdy | viz §5.3 | OVĚŘIT |
| `POST /api/assistant/jev-key` | nikdy (Nastavení nemá pole klíče) | klíče nastavené jinudy (`/api/assistant/status`: `configured: true`) | OVĚŘIT |
| `POST /api/access/logout` | nikdy (brána nemá tlačítko odhlásit) | – | OVĚŘIT (bezpečnost: nechat a doplnit tlačítko?) |
| `GET /api/oporahub/revisions/{identifier}` | nikdy | `opora_spec_revisions` 0 | PONECHAT s OporaHubem |

**Velikost OporaHubu.** 171 souborů / 14 777 řádků backendu (`backend/canvas/opora_*`,
`backend/api/editor/opora*_routes.py`, `backend/integrations/github_*`), 12 418 řádků testů, FE `frontend/hub/`
29 dílků / 9 198 řádků, 27 dokumentů / 4 141 řádků. Ani jeden řádek v jeho tabulkách nevznikl prací
člověka (§3).

## 2. Frontend

Vstup `index.html:25` → `frontend/app/components/main.tsx`. Knip (s testy jako vstupy) našel 7
nepoužitých souborů, `--production` dalších 4, které drží jen testy:

| Soubor | Řádky | Ztratil rodiče | Pozn. |
|---|---|---|---|
| `editor/node-detail/tree/components/NodeTree.tsx`, `TreeBlock.tsx` | 96 + 82 | `7465a5a` „mazání nepoužívaných funkcí karty“ | `BlockImages/State/Tags/Todos` dál používá `block-editor/components/BlockEditor.tsx:9-12` |
| `editor/node-detail/tree/styles/tree.css` | – | importuje ho jen `NodeTree.tsx:9` | **chyba:** nasazené `dist/assets/index-Bo3NUgSe.css` obsahuje z `.tree-*` jen `.tree-more/.tree-note/.tree-visibility` (z jiných souborů) → části editoru bloku jsou bez stylu |
| `editor/component-library/node-library/components/NodeLibraryDrawer.tsx`, `LibraryContext.tsx`, `logic/library-model.ts(+test)` | 134 + 86 + 85 | `eafc410` „Smazány nepoužívané sekce Knihovna“ | `styles/node-library.css` importuje `App.tsx:50` a třídy `node-library__*` používá `block-editor/components/BlockEditorDrawer.tsx:5-8` → CSS zůstává |
| `hub/oporahub-review-gate/components/CardReviewGate.tsx` | 74 | #28 `928fced` (šuplík karty) | `logic/gate-view.ts`, `review-gate.ts` používá `review-tab` |
| `editor/node-detail/rounds/logic/use-decision-rounds.ts` | 24 | #28 | `rounds-model.ts` dál používá `card-model.ts`, `types.ts` |
| `editor/llm-control/project-memory/logic/rule-batch.ts` | 42 | nikdy nepřipojen (`bd16f73`) | viz položka 6 |
| `editor/llm-control/editor-context/components/SpecificationDiff.tsx`, `logic/specification-diff.ts(+test)` | 17 + 46 | #30 `b9e761c` | #36 `9da9989` ho týž den upravil → souběžné PR |
| `editor/canvas/node-card/logic/evidence-readiness.ts(+test)` | 34 | #30 | – |
| `shared/desktop-state/logic/api.ts`: `previewPacket`, `snapshotPacket`, `assertSnapshotReadback`, `fetchSnapshot`, `exportExternalTask` | – | `7465a5a` | jdou s B4 |

Vzor: tři úklidové PR (`eafc410`, `7465a5a`, #30/#28) mazaly UI, ale nechaly backend, logiku a CSS.
Doporučení pro `docs/cista-linie.md`: úklid UI končí knipem a hledáním rout bez volajícího.

## 3. Data

Počty řádků přes 12 DB (soubor `db_counts.txt` v scratchpadu). Projekty: 13 v registru, 12 složek s DB.

| Oblast | Tabulky | Řádky (projekty) | Výklad |
|---|---|---|---|
| Plátno a stav | `desktop_v3_state` 11 (10), `node_spec_revisions` 607 (6), `node_text_revisions` 580 (7), `canvas_versions` 378 (7) | používá se | PONECHAT |
| Agenti (starý protokol) | `agent_result_records` 490 (5), `assignment_snapshots` 548 (5), `agent_workspace_revisions` 201 (4), `card_leases` 1 | používá se | PONECHAT |
| Schránka | `brief_fragment_revisions` 1 508 (6), `brief_gate_proposals` 661 (1), `brief_lessons` 66 | používá se | PONECHAT |
| OporaHub v2 | 64 tabulek `opora_*` | **0** ve všech | nezavedeno, viz níže |
| OporaHub v1 | `opora_commits` 22 (jen `ample`, 1 karta), `opora_events` 19 (3) | slabě | `opora_events` plní office (PR, worker, memory) |
| Prázdné s kódem | `card_rounds`, `check_runs`, `port_spawns`, `brief_lesson_events`, `workspace_graph_authority` | 0 | OVĚŘIT po funkcích (#11, #15) |
| Prázdné bez kódu | `node_sessions`, `agent_bindings`, `agent_binding_scopes`, `agent_activity_entries` | 0, v kódu 0 odkazů | ODSTRANIT (B8) |

**OporaHub: „nepoužité“, nebo „nezavedené“?** Nezavedené. Důkazy:
- Office je napojen: `agent-office/src/server/opora/execution-client.ts:56` (`/executions/claim`),
  `review-client.ts:42`, `isolated-observer.ts:28`, `pr-lens.ts:140`, `self-checks.ts:126`.
- Office přesto nikdy nespustil execution: `activity_log` nemá jediný `/api/oporahub/executions/claim`.
  Podle `agent-office/docs/opora-execution.md:9-13` bez přijaté revize zadání („missing accepted baseline“)
  odmítne převzetí a starý protokol nepoužije; `opora_spec_revisions` = 0 ve všech projektech.
- Lidé OporaHub UI nepoužili: 0 lidských zápisů do `/api/oporahub/*` za celou dobu logu.
- Agenti jedou starým protokolem: `/desktop-v3/lease` 1 339×, `/agent-output` 630×, `/brief-vault` 1 900×.

Jediný provoz v OporaHubu jsou prázdné claimy review slotů (položka 21). Verdikt PONECHAT jen s rozhodnutím
vlastníka: buď pilot (přijmout první revizi zadání u jedné karty a pustit ji přes office), nebo zmrazit
další rozvoj, dokud pilot neproběhne. Mazat by bylo předčasné — kód je čerstvý (PR #9–#45 z 2026-10-22).

## 4. Agenti

**Co agenti skutečně volají** (`activity_log`, zápisy): `review-jobs/claim` 3 668, `brief-vault` 1 900,
`lease` 1 339, `agent-output` 630, `canvas-versions` 176, `canvas-plan` 152, `pipeline` 83,
`agent-workspace` 65, `canvas-layout` 64, `rule` 61, `node-text` 51, `node-spec` 26. Z OporaHubu jen claim.

**Co agenti čtou z `node-brief`** (vzorek `ample`, karta `4f546c54…`, 100 315 B, 0,24–0,39 s):

| Pole | Velikost | Čte kód | Pozn. |
|---|---|---|---|
| `orientation` | 27 491 B | FE (`card-brief`) | `orientation.boundaries`, `.blocks`, `.harness` jsou **bajtově shodné** s horními poli |
| `boundaries` | 25 664 B | FE | 25 570 B je `proposedRules`: 115 návrhů, **všechny `scope: node` s cizím `target`** (`node_brief.py:370` nefiltruje) |
| `context` | 22 826 B | model (`--raw`) | `decisions` 18 824 B |
| `specification` | 13 419 B | model | `drawings` 9 120 B (prompt office `sketches.ts:65` je čte) |
| `outputContract` | 7 597 B | `opora_closure.py:199`, `opora_stage.py:175` (`.request`) | potřebné |
| `pipeline`, `evidence`, `loop` | malé | `opora_stage.py:98,179`, office `boss-attention/index.ts:106-116` | potřebné |
| `goal`, `usage`, `content`, `node` | malé | `opora_read.py:220-239` souhrn | potřebné |
| `harness.phase` | **neexistuje** | `opora_read.py:229` | souhrn vždy ukáže `phase: null` (položka 25) |
| `rounds`, `previousRounds`, `autonomy`, `resultHistory`, `processSync`, `checklist`, `fragments`, `lessons`, `ideas`, `trust`, `communication` | 0,1–1 kB | žádný kód (jen model přes `--raw`) | OVĚŘIT u modelů; levné, nechat |

Návrh (NAHRADIT, položka 7): `proposedRules` filtrovat stejně jako `effectiveRules` (projekt, cesta nad kartou,
`target == nodeId`) a v `orientation` místo kopie `boundaries` dát odkaz na horní pole. Ve vzorku to ubere
~51 kB z 100 kB na každé čtení briefu (agent, office boss-attention, FE card-brief).

**Skill opora-control-center** dokumentuje hooky (`references/hooks.md`) a `packet` — s B3/B4 odstranit.

## 5. Nefunkční

### 5.1 Dva padající testy (kořenová příčina)

Testy: `backend/api/project/test_graphify_routes.py::test_generate_uses_official_graphify_and_persists_output`
a `backend/project/maps/test_map_refresh.py::test_real_graphify_refresh_publishes_only_selected_project`.

1. **Prostředí (oba testy).** `graphify_runtime.runtime()` (`backend/project/maps/graphify_runtime.py:55-71`)
   hledá Python s `graphifyy==0.9.24` v pořadí `OPORA_GRAPHIFY_PYTHON` → `.venv-graphify` → `shutil.which('python')`
   → `sys.executable`. Pod `uv run pytest` je první `python` na PATH projektové `.venv`, které `graphifyy`
   nemá (není v `pyproject.toml`); `.venv-graphify` neexistuje. Proměnnou `OPORA_GRAPHIFY_PYTHON` nastavuje
   jen spouštěč `tools/opora.py:27-29` z `opora.local.toml [integrations] graphify_python` (v hlavní kopii
   ukazuje na `Python313`, kde `graphifyy` 0.9.24 je). Pytest ho nečte → 409 „Chybí graphifyy==0.9.24“.
   `tools/verify.py:32-47` oba testy vede jako `KNOWN_FAILURES`, takže pád je skrytý.
2. **Skrytá chyba v druhém testu.** S `OPORA_GRAPHIFY_PYTHON=…Python313/python.exe` první test **projde**
   (8,8 s), druhý padá dál na `test_map_refresh.py:219`: `assert manager.status(pb)['status'] == 'watching'`,
   skutečnost `'unavailable'`. Projekt B nikdy nevstoupil do fronty (test nevolá `scan()`, `retry` jen pro A),
   a `map_refresh.py:232` pro projekt bez řádku vrací `'unavailable'`. Aserce nebyla nikdy vykonána, protože
   test dřív padl o řádek výš.

Oprava (B6): (a) `runtime()` čte i `opora.local.toml` přes `tools/opora.load_config` (server spuštěný bez
spouštěče pak funguje stejně), nebo `backend/conftest.py` mapuje `[integrations] graphify_python` na env;
(b) oba testy dostanou `pytest.mark.graphify` se `skipif`, když `runtime()` hodí `ArtifactUnavailable` — místo
pádu jasný skip; (c) `test_map_refresh.py:219` → `== 'unavailable'` (B se nesmí dotknout), případně ověřit
`not (b / 'graphify-out').exists()` jako dnes; (d) smazat `KNOWN_FAILURES` z `tools/verify.py`.

### 5.2 Automatická aktualizace map (model č. 1) neběží nikde

`map-refresh/state.sqlite`: všech 5 zapsaných projektů má `status = failed` s chybou
„Snapshot vyžaduje 1–800 textových souborů a nejvýše 8 MiB“ (Opora 4b38182c naposledy 2026-10-22 23:50,
ample od 2026-10-14). Mez je v `backend/project/maps/map_refresh_snapshot.py:56`; snapshot nebere
`.graphifyignore` (jen pevné `EXCLUDED`), kdežto PR #41 zvedl Graphify na 1 200 souborů / 32 MiB
(`graphify_worker.py:20-21`) a ořez nechal na `.graphifyignore`. Opora `main` má 2 412 textových souborů.
Ruční Graphify funguje (9 lidských `POST /api/graphify/generate`). NAHRADIT (B7): snapshot vybírá soubory
přes stejný filtr `.graphifyignore` a sdílí konstanty mezí s `graphify_worker.py`; test na projekt
s >800 soubory a `.graphifyignore`.

### 5.3 Ostatní místa, kde aplikace spouští model

| Místo | Stav | Důkaz |
|---|---|---|
| Asistent (Claude Code) | funguje | `GET /api/assistant/status`: `available: true`, `claude 2.1.308`; 7 + 2 relace v logu |
| Směrovač Jev | nakonfigurovaný | `jev: {configured: true, provider: celeris}`; `/api/rlm/rank` volá `opora_read.py:338` |
| Zrcadlo | **nefunkční** | `opora.local.toml [mirror] enabled = true`, ale `127.0.0.1:8750` odmítá spojení (`curl` exit 7), `health: null`; 298 událostí jen 2026-10-14 22:07 → 10-15 10:50; průměrná přesnost 0,31; UI nemá volajícího. OVĚŘIT: vypnout `enabled`, nebo odstranit (`docs/zrcadlo.md`, klient, tabulka `brief_mirror_events`) |

### 5.4 Značky a dokumentace

- `TODO/FIXME/nefunkční` v kódu: žádné skutečné (výskyty jsou doménové „TODO“ bloků).
- `tools/doc_check.py`: 277 odkazů na neexistující cesty; 76 s prefixem `backend/|frontend/|tools/`, z toho
  většina v `docs/navrhy/2026-10-14-struktura-tajemstvi-opory.md` (popisuje jiné repo — v pořádku).
  Opravit: `docs/panely-editoru.md:55,65` a `docs/rozvrzeni-editoru.md:95,103` (`frontend/layout/library-navbar/`,
  `agent-navbar/` neexistují), `docs/domeny-a-worktree.md:95` (`worktree_manager.py`),
  `docs/synchronizace-pravdy.md:280,282` (`sync_refresh.py`, `linear_client.py`), `backend/PROCESS-PLAN.md:70`.
- `docs/workflow-opora.md:34-35` hlásí Procesy („UI + agent, hotovo“) a Agent hooks („hotovo“) — obojí bez UI.

## Jednoznačné k odstranění — dávky na PR

Každá dávka je samostatné PR z čerstvého `origin/main`; ověření `uv run pytest backend`, `npm test`,
`npm run build` a `tools/structure_check.py`.

**B1 — FE sirotci editoru** (jen frontend, ~600 řádků)
- Smazat: `editor/node-detail/tree/components/NodeTree.tsx`, `TreeBlock.tsx`;
  `editor/component-library/node-library/components/NodeLibraryDrawer.tsx`, `LibraryContext.tsx`,
  `logic/library-model.ts`, `logic/library-model.test.ts`; `hub/oporahub-review-gate/components/CardReviewGate.tsx`;
  `editor/node-detail/rounds/logic/use-decision-rounds.ts`; `editor/canvas/node-card/logic/evidence-readiness.ts(+test)`.
- Zároveň opravit: import `@/editor/node-detail/tree/styles/tree.css` přesunout do `BlockEditor.tsx`
  (dnes se nenačítá). `node-library.css` ponechat (používá `BlockEditorDrawer`).
- Proč bezpečné: knip potvrzuje, že je nic neimportuje mimo vlastní testy; `git log -S` ukazuje, kdy rodič zmizel.
- Testy: smazat `library-model.test.ts`, `evidence-readiness.test.ts`; upravit README složek `tree/`,
  `node-library/`, `rounds/`, `oporahub-review-gate/`. Screenshot editoru bloku před/po (styl stavu, štítků, TODO).

**B2 — Drobné routy a závislost** (~40 řádků)
- `GET /api/desktop-v3/tags` (`desktop_v3_routes.py:259`), `GET /api/node-spec/history` (`node_routes.py:48`),
  `prettier` z `package.json` (+ `npm install` pro lock).
- Proč bezpečné: žádný volající ve FE, skillu, tools ani office; `git log -S` je ve FE nikdy nenašel.
- Testy: odstranit jejich případy v `backend/api/editor/test_*`; `test_skill_docs.py` hlídá seznam rout ve skillu.

**B3 — Agent hooks** (~1 050 řádků + 412 testů)
- `backend/agent_control/` (celý), `backend/api/editor/hook_routes.py`, `hook_install_routes.py`,
  `backend/agent_installation/vscode_installer.py(+test)`, `tools/opora_hook.py(+test)`, registrace v
  `backend/app/factory.py`, výjimka loopback v `backend/app/remote_access.py`,
  `.claude/skills/opora-control-center/references/hooks.md`, řádek v `docs/workflow-opora.md:35`,
  zmínky v `docs/asistent.md:208`, `docs/vzdaleny-pristup.md`.
- Proč bezpečné: UI smazáno 2026-10-14 (`eafc410`), `hooks.sqlite` 0 vazeb a 0 událostí, `clients/` prázdné.
- Data: `P:/opora-data/agent-control/` nechat, smaže vlastník ručně po nasazení.

**B4 — Balíček pro agenta a externí export**
- Routy `desktop_v3_routes.py:335-353` (`packet/preview`, `packet/snapshot`, `packet/snapshots/{id}`,
  `external-export` GET/POST), `backend/editor/agent_handoff/external_agent_tasks.py`, FE funkce v
  `shared/desktop-state/logic/api.ts:77-135`, příkaz `packet` v `opora_read.py:511`.
- Proč bezpečné: UI smazáno `7465a5a`; poslední snímek 2026-09-11; agenti v logu packet nevolali.
- Pozor: `desktop_v3_packets.py` zůstává, pokud ho používá `node_brief` (ověřit importy); tabulku
  `desktop_v3_snapshots` zatím nemazat.

**B5 — Starší procesy**
- `backend/api/editor/process_routes.py`, `backend/editor/process/process_lifecycle.py`, `process_reports.py`
  (+testy), registrace ve `factory.py`, řádek `docs/workflow-opora.md:34`.
- `ProcessStore` čtou `backend/canvas/sync_report.py:129` a `opora_execution_process_guard.py:26`; guard hlídá
  právě `/api/processes` → s routami zmizí i guard a `test_opora_execution_processes.py`.
  `sync_report` přepnout na prázdný seznam, nebo `ProcessStore` ponechat jen pro čtení historie (rozhodnutí v PR).
- Proč bezpečné: jeden soubor z 2026-09-14, žádný volající nikdy.

**B6 — Testy Graphify** (§5.1) — `graphify_runtime.py`, `backend/conftest.py`, oba testy, `tools/verify.py`.

**B7 — Snapshot map podle `.graphifyignore`** (§5.2) — `map_refresh_snapshot.py`, sdílené meze s `graphify_worker.py`, nový test; `docs/mapy-projektu.md`.

**B8 — Migrace: mrtvé tabulky** — `DROP TABLE IF EXISTS node_sessions, agent_bindings, agent_binding_scopes,
agent_activity_entries` v `database/`; test migrace na kopii DB; záloha před nasazením.

**B9 — Mrtvé symboly Pythonu**
- `hook_validation.py:100 endpoint_is_loopback` (s B3), `canvas_index.py:26 ENTRY_KINDS`,
  `opora_agent_state_review_gates.py:13 VERBS`, `opora_content_sources.py:200 apply_content`,
  `opora_review_gate_rules.py:11 PENDING`, `desktop_v3_state.py:52 NODE_KEYS_WITH_BLOCKS`,
  `desktop_v3_packets.py:112 drawing_chain`, `process_reports.py:20 REPORT_ID` (s B5),
  `memory_service.py:200 set_celeris_key`, `project_folder.py:52 processes` (s B5).
- Proč bezpečné: grep přes `backend`, `tools`, `.claude` = jediný výskyt je definice.
- Nepatří sem (falešné nálezy): `commit_pairs.py:118 spec_saved_at` (kontrakt volajícího, docstring),
  `conftest.py:43` (autouse fixture), `newurl/req` v `*_client.py` (signatura `redirect_request`).

## OVĚŘIT — co rozhodnout

| Položka | Co ověřit |
|---|---|
| `confirm-proposals` (#4) | Chtěl #30 zrušit hromadné potvrzení sektoru? Bylo používané 37×. Ano → ODSTRANIT routu; ne → vrátit tlačítko do Velínu. |
| `SpecificationDiff` + `assignment-comparison` (#5) | Má se rozdíl zadání ukázat v šuplíku karty? #36 ho opravoval; jinak smazat obojí. |
| Kola karty (#11) | `card_rounds` 0 řádků, UI zrušeno #28; brief dál vydává `rounds`, `previousRounds`. Zrušit, nebo přenést do šuplíku? |
| `check-run` (#15) | Má skill po kontrolách volat `POST /api/check-run`, nebo stačí `checksRun` v `agent-output`? Pak odstranit i tabulku a čtení v sync-reportu. |
| `opora-merge` (#16) | Patří do OporaHub v1 (commity na rozsah); s rozhodnutím o OporaHubu. |
| Zrcadlo (#17) | Sidecar neběží 8 dní; vypnout `[mirror] enabled`, nebo smazat. |
| OporaHub v2 (#20) | Pilot na jedné kartě, nebo zmrazit. Do té doby přidat do office backoff claimů (#21). |
| `jev-key`, `access/logout` | Doplnit UI (pole klíče v Nastavení, tlačítko Odhlásit u vzdálené brány), nebo routy smazat. |
| Rozsah `node-brief` (#7) | Po filtru `proposedRules` změřit velikost briefu znovu a zkontrolovat, zda modely čtou `orientation` místo horních polí. |
