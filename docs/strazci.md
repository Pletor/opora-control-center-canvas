# Strážci: tichý dohled bez modelu

Stav: kontrakt, rozhodnutí uživatele 2026-10-28. Kód ho provádí, nemění.

## 1. Proč

Co jde spočítat, počítá kód (`docs/zive-zobrazeni-a-knihovna.md` §6). Strážci jsou deterministické procesy uvnitř
backendu OPORY, které běží nepřetržitě, bez člověka a bez modelu: **sledují** plátno a stavbu, **zaznamenávají**
vývoj, **upozorňují**, když se plán nebo stavba stáčí, a předávají zkušenost agentům (OpenViking). Nikdy nemění
zadání, kroky ani obsah karet a nikdy nepřijímají ani nezamítají návrhy – to dělá člověk nebo agent.

## 2. Jádro

- Jeden worker `GuardianManager` ve stejném vzoru jako ostatní (`backend/canvas/opora_auto_rebase_manager.py`):
  daemon vlákno, `threading.Event` stop, tick `OPORA_GUARDS_SECONDS` (výchozí 30 s), vypnutí
  `OPORA_GUARDS_WORKER=0` (testy). Start a stop v lifespan `backend/app/factory.py`. `opora.local.toml` sekce
  `[strazci]` (`enabled`, `seconds`) se převádí na proměnné prostředí v `tools/opora.py`.
- **Registr strážců**: každý strážce = `{id, label, every_s, run(ctx) -> list[Finding] | None}`. Worker spouští
  strážce, kterým uplynul interval, pro každý projekt. Výjimka strážce se zachytí, zapíše do jeho stavu
  (`lastError`) a nikdy neshodí worker ani ostatní strážce. Strážce, který přeskočí, protože se vstup nezměnil
  (hlava grafu, revize), stav neaktualizuje kromě `lastRunAt`.
- Logika v `backend/canvas/strazci/` (jeden modul na strážce + `registry.py`, `findings.py`, `manager.py`), test
  `test_<modul>.py` vedle s falešným časem. Router `backend/api/editor/strazci_routes.py`.

## 3. Nálezy

`Finding = {key, guard, rule, severity: "info"|"warn"|"block", message, nodeId?, journeyId?, executionId?, data?}`.
`key` je stabilní identita nálezu (např. `map:section.unrealized:<nodeId>:<sectionId>`).

- Tabulka projektu `guard_findings` (`key` PK, `guard`, `rule`, `severity`, `message`, `node_id`, `payload`,
  `first_seen`, `last_seen`, `resolved_at`). Strážce vrací **úplný** seznam svých aktuálních nálezů; jádro udělá
  diff: nový → vloží a vydá událost `guard.alert`, trvající → jen `last_seen`, zmizelý → `resolved_at` a událost
  `guard.resolved`. Opakování se nehlásí (žádná záplava). Vyřešené nálezy starší 14 dní se mažou.
- Události `guard.alert` / `guard.resolved` jsou v `KINDS` i `QUIET` (`backend/canvas/opora_events.py`), takže
  neobnovují kartu a jdou živým pásem (SSE) do velínu.

## 4. Strážci (první sada)

| id | každých | Co hlídá | Pravidla |
|---|---|---|---|
| `mapa` | 60 s, jen při změně hlavy architektury | kontrola mapy (`map_check`) nad přijatou architekturou | každý nález = finding (`severity warn`, `page.no-goal` a `journey.broken` `block` pro člověka, `page.intent-stale` `block`) |
| `prace` | 30 s | executions a nároky karet | `work.lease-expired` (nárok po termínu, karta dál „staví se“), `work.no-heartbeat` (běh bez zprávy déle než 10 min), `work.step-stalled` (krok `running` déle než 30 min) |
| `cesty` | 120 s | `lastRun` cest | `journey.failed`, `journey.stale`, `journey.blocks-card` (karta čeká na uzavření a brání jí brána `journeys`) |
| `pravda` | 300 s | synchronizace | `truth.worktree-behind` (worktree karty za `main` víc než 20 commitů), `truth.proposal-stale` (návrh grafu / změny čeká na člověka déle než 24 h) |
| `zkusenost` | při události | uzavření karty (`done.confirmed`), doklad cesty, sloučení PR | deterministický záznam `{card, role, co prošlo, co spadlo a čím opraveno, čísla kroků, odkaz na doklad}` do OpenViking pod klíčem role přes outbox stejně jako `harness_memory` (claim/lease, retry); nehlásí nálezy |
| `trend` | 900 s | souhrnná čísla | vzorek do tabulky `guard_trend(project, at, metric, value)`: `holes`, `holes.agent`, `journeys.verified`, `journeys.total`, `cards.done`, `cards.building`, `work.stalled`, `proposals.waiting`; retence 90 dní |

Výklad G3 (2026-10-28): `zkusenost` nemá háček v místě události; tick strážce (každých 10 s) dočte od svého kurzoru
(`guard_experience_cursor`) nové `card.closed` / `merge.done` v `opora_events` a nové řádky `journey_runs`. První běh
v projektu nastaví kurzor na hlavu bez doplňování historie. Outbox je vlastní tabulka `guard_experience` (vzor
`harness_memory_deliveries`); role = `agentRole` karty na ploše, karta dokladu cesty = první stránka cesty. Nejvýš 2
zápisy na projekt a tick, první nedostupnost OpenVikingu doručení v ticku ukončí. Tabulka trendu má sloupec
`project_id` (jako ostatní tabulky projektu); `work.stalled` = otevřené nálezy strážce `prace`, `cards.building` =
poslední vydaná etapa karty rozpracovaná (běh, doklad, review, PR, merge) a karta není uzavřená.

Strážce smí **sám** udělat jen vratnou akci mimo obsah: první sada žádnou nedělá (jen hlásí); propadlý nárok
uvolní až příští claim jako dnes.

## 5. Kde se to odráží (fraktálně)

**Jeden zdroj děr mapy.** Díry mapy počítá jen kontrola mapy; agentům je dává `mapGaps` (agent-state) a `holes`
(brief) podle `docs/architektura-pro-agenty.md` §5.1. Strážce `mapa` je ukládá jako nálezy kvůli **změnám**
(událost nová / zaniklá díra), odznakům a trendu; `guards` v agent-state a v briefu pravidla mapy (`guard: "mapa"`)
**vynechají**, aby agent ani člověk neviděl stejnou díru dvakrát. Totéž platí pro `journey.failed` a `journey.stale` strážce `cesty`
(kontrola mapy je hlásí jako `journey.unverified`); nálezy vznikají kvůli událostem a trendu, agentovi je dává jen `mapGaps`.

- `GET /api/strazci?project=` → `{guards: [{id, label, every_s, lastRunAt, lastOkAt, lastError?, open}], open:
  {block, warn, info}}`; `GET /api/strazci/findings?project=&node=&open=1`; `GET /api/strazci/trend?project=&metric=&days=`.
- **agent-state** přidá `guards: {open: {...}, findings: [top 20 otevřených, block první]}`; karta v `cards[]`
  dostane `guardFindings` (počet a nejvyšší závažnost).
- **node-brief** dostane `guards: [{rule, message}]` (nejvýš 3 otevřené nálezy karty) mimo `specification`
  (nemění `contextVersion`).
- **Velín:** řádek „Strážci ✓ / ⚠ N“ s posledním během a seznam otevřených nálezů (klik → karta), panel Trend
  (malé křivky z `guard_trend`).
- **Studio a Architektura:** karta s otevřeným nálezem strážce nese odznak (počet, barva podle závažnosti) ve
  Skutečnosti Studia, v Editoru stránky i na Mapě domény; rodič ve fraktálu sčítá nálezy dětí jako díry.
- **Skill** `opora-control-center`: reference `strazci.md` (co znamená který nález a co s ním má agent udělat).

## 6. Etapy

| PR | Obsah |
|---|---|
| G1 | jádro (registr, worker, tabulka `guard_findings`, diff, události, `GET /api/strazci*`) + strážci `mapa` a `prace` |
| G2 | strážci `cesty` a `pravda`; agent-state `guards`, node-brief `guards`; velín řádek a seznam |
| G3 | `zkusenost` (OpenViking) a `trend` (tabulka, endpoint, panel ve velínu) |
| G4 | odznaky ve Studiu a Architektuře, skill reference |
