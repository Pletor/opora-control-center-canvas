# Domény nad worktree – kontrakt

Stav: **návrh ke schválení** (2026-10-14). Kód tento kontrakt provádí, nemění ho.

## 1. Proč

Architektura projektu (domény a hlavní strom stránek) dnes žije v grafu jednoho pracovního prostoru. U Git projektu je `main` jen pro čtení (`backend/canvas/canvas_service.py` `_view`, `readOnly: wid == "main"`), takže na čistém mainu nejde založit doménu a tlačítko „+ Doména“ se jen zašedne bez vysvětlení (`frontend/project/architecture-editor/landing/components/ArchitectureLanding.tsx`). Každý worktree navíc vidí jen vlastní kopii domén.

Cíl: **architektura je nadřazená worktree.** Je jedna pro projekt, jde upravit z mainu i z kteréhokoli worktree, každý worktree patří jedné doméně a přehled ukazuje, co se na které doméně děje a jestli web běží.

## 2. Pojmy

| Pojem | Význam |
|---|---|
| **Architektura** | Uzly se `site` (domény `site.kind="application"`, stránky `site.kind="page"` s klíči `{kind, path[, goal, feel, navLabel, sections]}`), strukturní sektory mezi nimi a hrany mezi dvěma uzly architektury. Jedna pro projekt. |
| **Doména** | Sektor `site.kind="application"` s **právě jedním** prostředím `{name, host}` (platí už dnes, `docs/architektura-projektu.md`). Skupina na přehledu = `name` prostředí (Produkce / Vývoj). |
| **Obsah stránky** | Všechno pod stránkou, co nemá `site` (karty, sektory práce, oblasti). Patří pracovnímu prostoru. |
| **Worktree** | Řádek `workspaces` + Git worktree. Patří jedné doméně přes `workspaces.node_id = id domény`. |
| **Relace** | Živá práce ve worktree: lease karty (převzetí a aktivita). |

## 3. Domény Tajemstvi-opory

| Skupina | Host | Druh (`domain-kind.ts`) | Health cesta |
|---|---|---|---|
| Produkce | `www.tajemstviopory.cz` | web | – |
| Produkce | `app.tajemstviopory.cz` | app | `/api/v1/health` |
| Produkce | `admins.tajemstviopory.cz` | admin | – |
| Vývoj | `www.tajemstviopory.dev` | web | – |
| Vývoj | `app.tajemstviopory.dev` | app | `/api/v1/health` |
| Vývoj | `admins.tajemstviopory.dev` | admin | – |

- Veřejný web má kanonický host s `www` (`infrastructure/cloud/CLAUDE.md` v repu TO; adresa bez `www` na něj přesměruje). Pro `.dev` platí stejná symetrie.
- Health cesta podle backendu TO: `GET /api/v1/health` bez přihlášení, vrací `{"status":"ok"|"degradovano"|"nedostupno","env",…}` a 200/503. Commit neobsahuje.
- Ověřeno 2026-10-14: žádný ze šesti hostů zatím neodpovídá (`tajemstviopory.cz` má zónu u Wedosu bez záznamu A, ostatní NXDOMAIN, `.dev` není delegovaná). Přehled to musí umět ukázat jako normální stav, ne jako chybu.
- Domény se v aplikaci jen evidují a sledují. DNS, nasazení ani GitHub aplikace nekonfiguruje.

## 4. Úložiště architektury

Nové tabulky v `project.sqlite` (`database/schema/project_schema.py`):

```
project_architecture(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, graph TEXT NOT NULL,
                     updated_at TEXT NOT NULL, actor TEXT NOT NULL)
project_architecture_revisions(project_id TEXT, revision INTEGER, graph TEXT, actor TEXT, workspace TEXT,
                               created_at TEXT, PRIMARY KEY(project_id, revision))
```

- `graph` = `{nodes, edges}` jen s uzly architektury, stejný formát a validace jako graf plátna.
- Revize jen přibývají; tabulka revizí je historie i návrat.
- Stejný model pro všechny druhy projektů (Git, lokální, prázdný). Lokální projekt drží v `drafts.graph` jen obsah.

### Složený pohled (překryv podle ID)

- `/api/view` vrací **architektura ∪ obsah pracovního prostoru**. Obsah na architekturu odkazuje `parentId` nebo hranou. Digest pohledu se počítá ze složeného grafu, takže stávající klient funguje.
- U Git mainu se obsah čte dál z `HEAD:opora-canvas.json`; uzly se stejným ID jako v architektuře se při skládání skryjí (vyhrává architektura).
- `save_graph` a `apply_plan` rozdělí příchozí složený graf: uzly z množiny ID architektury nebo se `site` → architektura (`revision+1`), zbytek → obsah prostoru. Obojí pod `graph_lock_for(pid)`. Souběžná změna architektury z jiného okna se projeví jako dnešní konflikt digestu („Plátno se změnilo v jiném okně“).
- Uzel se `site` smí ležet jen v architektuře; uložení ho tam přesune.
- `validate_sites` (`backend/canvas/site_metadata.py`) zůstává jedna funkce: volá se nad architekturou při zápisu architektury a nad složeným grafem při `save_graph`. Unikátnost hostů a cest je tím celoprojektová.
- `site` aplikace smí nově nést volitelné `healthPath` (ověřené jako cesta přes `route_key`): klíče `{kind, environments[, healthPath]}`.
- `site` stránky: klíče `{kind, path[, goal, feel, navLabel, sections]}`. `goal` 1–200 znaků, `feel` 1–120, `navLabel` 1–40,
  bez řídicích znaků; prázdný řetězec je chyba (pole se vynechá). `sections` 1–20 položek přesně `{id, role, name, intent}`:
  `id` ve tvaru id uzlu a jedinečné ve stránce, `role` ∈ `hero | cta | form | content | gallery | proof | faq | footer | custom`,
  `name` 1–60, `intent` 0–200. Výchozí hodnoty se nikdy nedoplňují (`docs/architektura-pro-agenty.md` §3.1).

### Pravidla zápisu

| Pohled | Architektura | Obsah |
|---|---|---|
| Git `main` | **zapisovatelná** | jen pro čtení (beze změny) |
| Git worktree | zapisovatelná | zapisovatelný |
| Lokální / prázdný projekt (`draft`) | zapisovatelná | zapisovatelný |

- Pohled vrací dál `readOnly` (pro obsah) a nově `architectureEditable` + `architectureRevision`. Těch ~40 kontrol `readOnly` v backendu (karty, deník, leases, desktop v3) se nemění.
- Na mainu `save_graph` projde jen tehdy, když se obsah nezměnil; `apply_plan` jen s plánem, který mění čistě architekturu, a bez zápisu stavu Desktop v3.
- Zadání (`node_spec`) a text (`node_text`) uzlů architektury se ukládají pod rezervovaným `wid = "architecture"`. Práce na stránce (leases, deník, desktop v3) zůstává v prostoru.

### Odstranění a návrat

- `/api/removal-preview` a `/api/remove` u uzlu architektury projdou obsah všech prostorů projektu a `workspaces.node_id`. Když na uzel něco odkazuje, odstranění se odmítne a náhled vypíše dotčené worktree.
- Undo (`save_graph(undo=True)`) používá stejné rozdělení. `canvas_versions` dál ukládají složený snímek, obnova vrací jen obsah; architekturu vrací `POST /api/project-architecture/restore` podle revize.

## 5. Migrace

Modul `backend/canvas/migrate_architecture.py` + `test_migrate_architecture.py`, vzor `migrate_to_project_folders.py`.

1. Zdroje: `drafts.graph`, všechny `canvas/workspaces/<wid>/graph.json`, u Gitu `HEAD:opora-canvas.json` jen čtením. Pro prostor převedený návrhem grafu OporaHubu se místo souboru čte autoritativní graf z SQLite; odstranění uzlů architektury se zapisuje tamtéž.
2. Vybrat uzly se `site`, jejich předky ke kořeni domény a hrany mezi nimi. ID zůstávají.
3. Stejné ID se stejným obsahem → jeden záznam. Stejné ID s rozdílným obsahem → **žádné slučování**: projekt se přeskočí a vrátí se `conflicts[]`.
4. Záloha před zápisem do `projects/<id>/canvas/backups/architecture-<čas>/`.
5. Zapsat revizi 1, uzly architektury odebrat z grafů prostorů, zkopírovat (ne přesunout) jejich `node_spec_revisions` a `node_text_revisions` pod `wid = "architecture"` i s historií.
6. Idempotentní (existuje-li `project_architecture`, nic nedělá), `dryRun` vrací report. `down()` odmítne obnovu po uložení návrhu grafu nebo přijetí plánu OporaHubu, zavedení databázové autority grafu nebo řízeného vykonávání, aby nevrátil stará oprávnění a nezahodil přijaté plány. Při povolené obnově starší zálohy znovu doplní kompatibilní schéma i na již otevřeném spojení; databáze proto nemusí být bajtově shodná se zálohou.
7. Spouští se ručně přes API/nástroj, nejdřív `dryRun`, s backendem nad zálohovanými daty. Nad `P:\opora-data` se pouští až po schválení reportu.

## 6. Worktree a doména

- `create_workspace` ověří, že `nodeId` je doména v architektuře; jinak 400. Modal „Nový worktree“ předvyplní aktuální doménu.
- Existující worktree s `node_id = "project"` (u TO `a0f1764b`, aktér `01-start-projektu`) se ukazují ve skupině **Nepřiřazené** a jdou přiřadit přes `PATCH /api/workspaces/{wid}`.
- `close_workspace(pid, wid, reason, confirmed)` = **přesun do skladiště** (§13.3): odmítne, když je worktree `dirty` nebo má živou relaci (§7); jinak `git worktree remove` bez `--force`, **větev `work/<wid>` zůstane**, řádek `workspaces` se přesune do `archived_workspaces(id, project_id, node_id, branch, actor, base_sha, reason, archived_at)` v registru, data prostoru do `canvas/workspaces/_archive/<wid>`. `GET /api/workspaces/archive?project=` vrací skladiště (jen čtení).
- `backend/project/worktrees/worktree_manager.py` a jeho test se smažou (mrtvý kód, jiné schéma ID, volají ho jen jeho testy); upravit `backend/project/worktrees/README.md` a odkaz v `docs/pravidla-struktury.md`.

### Posun worktree za main

Srdce čte kód z worktree prostoru (`worktrees/<8 znaků>`, větev `work/<id>`), který se po založení sám nehýbe a zastarává za `main`. Proto po úspěšné synchronizaci `main` v `watch_git` server posune každý hlídaný prostor git projektu (kromě domovského `main`) na HEAD mainu, ale **jen když platí vše**: složka worktree existuje, `git status --porcelain` je prázdné a HEAD worktree je striktní předek HEAD mainu (`git merge-base --is-ancestor`, a ne rovný). Pak `git merge --ff-only <sha mainu>`. Jinak se mlčky přeskočí (vlastní commity, špinavý strom, nečitelný stav); nikdy `--force` ani `reset`. Selhání jednoho prostoru se jen zapíše do logu a nerozbije průchod. Nový HEAD si supervisor zapíše do `heads[(projekt, prostor)]`, aby `_watch_head` nevyslal duplicitní vstup `commits` (posun mainu už prostory dostaly přes `_targets`). Kód: `backend/project/worktrees/workspace_fast_forward.py`.

## 7. Stav práce

Archivace se serializuje se změnami grafu a projektu. Databázové záznamy grafu,
přijatých plánů a vykonávání zůstávají zachovány pod původním ID prostoru;
samotná složka archivu není úplnou zálohou. Záloha musí zahrnovat také databázi projektu.

Logika `backend/project/architecture/work_status.py`, router `backend/api/project/project_architecture_routes.py`.

Zdroje: `card_leases` + `card_work_activity`. Relace starého asistenta jako zdroj zmizely s jeho smazáním (H2b2b, `docs/brain-heart-channel.md` §5).

| Stav worktree | Kdy (vyhrává vyšší řádek) |
|---|---|
| **běží** | platná lease a aktivita ≤ 300 s |
| **čeká** | platná lease bez aktivity v posledních 300 s |
| **stojí** | prošlá lease s aktivitou mladší 24 h |
| **bez relace** | nic z výše uvedeného (nikdy se nehlásí jako „stojí“) |

Doména = počty stavů jejích worktree + karty v práci (`nodeId` z leases). Odpověď nese `reasons[]`, aby UI umělo říct proč.

## 8. Stav webu

Klient `backend/integrations/web_probe_client.py`, logika a cache `backend/project/architecture/web_status.py`.

- **Vstup jen `project` (+ volitelně `domain`).** Hosty se berou výhradně z architektury; žádná URL z požadavku.
- Ochrany ve stylu `openviking_client.py`: bez proxy, přesměrování se nesleduje (3xx = běží, `Location` jako informace), timeout 3 s spojení / 5 s celkem, strop odpovědi 64 KB, nejvýš 4 souběžné kontroly a 20 hostů na projekt.
- Proti SSRF: po resolvování se odmítnou privátní, loopback a link-local adresy; spojení se připne na ověřenou IP (SNI = host).
- Kontrola běží **na dotaz** s cache 60 s na host; ruční obnovení nejdřív po 30 s. Výsledky jen v paměti, žádná historie.

| Stav | Text | Kdy |
|---|---|---|
| `dns_missing` | DNS neexistuje | NXDOMAIN nebo nejistý výsledek resolveru |
| `dns_no_web` | DNS bez webu | jméno existuje, ale bez A/AAAA, nebo 443 odmítnuto/vypršelo |
| `unreachable` | nedostupné | chyba TLS, 5xx, vypršení čtení, health `nedostupno` / 503 |
| `up` | běží | 2xx/3xx, health `ok` |
| `degraded` | degradováno | health `degradovano` |
| `unchecked` | neověřeno | ještě nekontrolováno |

## 9. API

| Metoda | Cesta | Payload → odpověď |
|---|---|---|
| GET | `/api/project-architecture?project=` | → `{graph, revision, digest}` |
| POST | `/api/project-architecture/restore` | `{project, revision, digest}` → totéž |
| POST | `/api/project-architecture/migrate` | `{project, dryRun}` → `{moved[], conflicts[], backup}` |
| GET | `/api/project-architecture/work-status?project=` | → `{domains:[{id, name, environment, counts, worktrees:[{id, branch, actor, createdAt, state, reasons[], sessions[], cards[{nodeId, name}]}]}], unassigned:[…]}` |
| GET | `/api/project-architecture/web-status?project=&domain=&refresh=` | → `{hosts:[{domainId, environment, host, state, httpStatus, health, latencyMs, checkedAt, detail}]}` |
| POST | `/api/workspaces` | beze změny tvaru; `nodeId` musí být doména |
| PATCH | `/api/workspaces/{wid}` | `{project, nodeId}` → workspace |
| POST | `/api/workspaces/{wid}/archive` | `{project, reason, confirmed: true}` → `{archived, branch}` |
| GET | `/api/workspaces/archive?project=` | → `{items:[{id, nodeId, branch, actor, reason, archivedAt}]}` |
| GET | `/api/project-workspaces` | položky navíc `nodeId`, `domainName` |
| GET | `/api/view` | navíc `architectureEditable`, `architectureRevision` |

Routery jen v `backend/api/project/`, logika v modulech, test `test_<modul>.py` vedle.

## 10. Frontend

### Tok

1. **Přehled domén** (`ArchitectureLanding`): pruhy Produkce / Vývoj a Nepřiřazené. Karta domény nese žeton webu („běží · 120 ms“, „DNS neexistuje“), počty „3 worktree · 1 běží · 1 čeká“ a sbalitelný strom worktree (větev → aktér → karty v práci).
2. **Detail domény** (`ArchitectureDomainMap`): vlevo strom stránek, uprostřed mapa stránek (na `PageCard` odznak „2 worktree“), vpravo živý panel (web hostu + strom worktree se stavy relací). Detail vybraného worktree nabízí „Zadat srdci“ pro worktree i pro každou kartu v práci: App pošle připravený text `POST /api/brain/heart/messages` a otevře panel asistenta.
3. **Plátno stránky** (`PageEditor`): beze změny, v hlavičce žeton webu.

- Klik na worktree ve stromu **nepřepíná** prostor, jen ho vybere a zvýrazní dotčené stránky. Přepne až tlačítko „Pracovat v tomto worktree“ → `onSwitchWorkspace(id)` nahoru do `App` (stejný kód jako `onSelectWorkspace`).
- Editor architektury se klíčuje jen `[project]` (`ProjectWorkspace.tsx`); prostor se předává do plátna stránky.

### Dílky

| Složka | Obsah |
|---|---|
| `project/architecture-editor/live-status/` (nová) | `WebStatusBadge`, `SessionChip`, `WorktreeTree`, `WorktreeRow`, `LiveDomainPanel`; `logic/live-model.ts`, `web-status.ts`, `session-state.ts`, `live-poll.ts` + testy; `styles/live-status.css`; `README.md` |
| `landing/` | `DomainCard` dostane `live?`; nový `DomainLockNote` (řekne, proč je akce zakázaná) |
| `domain-map/` | `ArchitectureDomainMap` dostane slot `live`, `PageCard` `workCount` |
| `logic/use-project-architecture.ts` | čtení/zápis architektury s vlastním digestem; `architectureEditable` místo `view.readOnly` |
| `logic/use-domain-live.ts` | jediné místo, které načítá stav práce a webu; jen přes `usePolling` (10 s v detailu, 30 s na přehledu, odstup 10 → 20 → 60 s, ve skryté záložce stojí) |

- Data drží `ArchitectureEditor`; dílky nevolají `fetch`, změny hlásí callbackem.
- `shared/hooks/logic/poller.ts` dostane volitelné `intervalMs: number | (() => number)` + test; žádný vlastní časovač (`poller.test.ts` hlídá holý `setInterval`).
- `project-capabilities.ts` dostane `worktreeLive: boolean` (`!localProject`); lokální projekt živý panel nevykreslí. Dílek dál nečte `sourceKind`.
- CSS: blok `live-status` (BEM, příběhový komentář), tvar žetonů převzatý z `agent-summary__work`; stav nese slovo + ikonu + `title`, nikdy jen barvu. „DNS neexistuje“ je neutrální, ne červené. Strom `role="tree"`, panel `aria-live="polite"` jen při změně stavu.
- Prázdné stavy: „Na této doméně se teď nepracuje.“ + „Nový worktree“; chyba načtení nechá poslední data s časem „údaj z 12:03“.

## 11. Pořadí práce (fáze 2)

| Kus | Obsah | Závisí na |
|---|---|---|
| B1 | úložiště architektury, složený pohled, rozdělení v `save_graph`/`apply_plan`, pravidla zápisu, `healthPath`, odstranění/undo | – |
| B2 | stav práce (`work_status`) + endpoint | – (paralelně s B1) |
| B3 | stav webu (`web_probe_client`, `web_status`) + endpoint | – (paralelně s B1) |
| B4 | worktree ↔ doména, PATCH/DELETE, smazání `worktree_manager` | B1 |
| B5 | migrace + dry-run nad kopií dat | B1 |
| F1 | `use-project-architecture`, „+ Doména“ na mainu, `DomainLockNote`, schopnosti | B1 |
| F2 | `live-status` dílky, landing, mapa, poller | B2, B3 (tvar API z §9) |
| D1 | migrace živých dat po schválení reportu, založení šesti domén TO | B5, F1 |

Každý kus: kontrakt, seznam souborů, `uv run pytest backend tools`, `npm test`, `npm run build`, zákaz sahat mimo scope a na `P:\opora-data`.

## 12. Teď nestavět

Ovládání relací z panelu, push/SSE, historie dostupnosti a grafy, nasazování a DNS, export architektury do gitu, automatické slučování konfliktů migrace, merge/úklid worktree.

## 13. Rozhodnutí člověka (2026-10-14)

Pozdější kontrakt [OporaHubu](oporahub.md) rozděluje autoritu: přijaté plány jsou
v Canvasu, kód a jeho review v GitHubu. Níže uvedený plán exportu do Gitu je
historické rozhodnutí, nikoli současný předpoklad vykonávání. Manifest grafu
zachycuje kontext sdílené architektury; její samostatné workflow tím není nahrazeno.

1. **Vývoj je jiný než Produkce.** Šest samostatných domén s vlastními stromy. Ve Vývoji vznikají nové věci; do Produkce se převádějí, až mají kvalitu. Převod Vývoj → Produkce je pozdější kus (zde se jen nesmí znemožnit: ID se nesdílejí, převod bude kopie s vazbou `promotedFrom`).
2. **Architekturu lze měnit odkudkoli.** Pravda je to, co projde workflow a mergne se do mainu (`docs/oporahub.md`: „co není v gitu, není hotové“). Architektura projektu v OPORA je pracovní kopie; každá revize nese `actor` a `workspace`, odkud přišla. Export domén a stránek do plánu v repu dělá OporaHub (pozdější kus).
3. **Uzavřený worktree jde do skladiště OporaHubu.** Větev `work/<wid>` zůstává, záznam se přesune do archivu (`archived_workspaces`: id, doména, větev, aktér, důvod, čas) a neovlivňuje aktivní práci. Typicky nápad, který nevyšel. Ze skladiště jde jen číst; obnova je pozdější kus.
4. **Práce ve worktree řídí srdce.** Člověk píše srdci v panelu asistenta (`docs/brain-heart-channel.md`); živý panel nabízí „Zadat srdci“ u worktree i u karty (připravená zpráva srdci). Pracovníky do worktree posazuje srdce úkolem přes bránu (`docs/brain-gate.md`). Dřívější „Nová relace“ starého asistenta je od H2b2b pryč. Prahy z §7 (300 s / 24 h) a cache webu 60 s platí.
