# Karta DNA – čistá karta na plátně a popup se vším o kartě

Zadání uživatele 2026-10-08: „Karty potřebuji čisté. Když se karta rozklikne, vyskočí popup, kde budou
všechny podrobnosti a to, co po mně chceš, abych se rychle orientoval a měl vše na jednom místě.
Proklikat hlavní záložky a nemít takto velké karty. Padá mi z toho prohlížeč kvůli paměti.“
Popup je „DNA karty“: proces chronologicky i sémanticky, workflow a pipeline, propojení s GitHubem
a OporaHubem (aktuální kód a verze zadání, kdy to sedí a výstup funguje v prohlížeči). Když LLM dostane
stejnou kartu znovu, postaví ji podle všech zaznamenaných dat a cesty.

Vzor problému: karta 2.10 projektu ample (screenshot `image12.png` v kořeni hlavního repa) – na kartě
je editor důkazů s každým `checksRun` jako 5 inputů; při výběru více karet se editory mountují všem.

## 1. Karta na plátně (kompaktní, bez editorů)

Zobrazuje jen to, co je vidět na první pohled (infografika před prózou):

- hlava: typ (`[task]`…), název, stav (`ready`/`claimed`/`done`), vrstva; odznak „čeká na tebe“;
- proužek kontrolního pásu (`CardChecklist`, 10 buněk) – beze změny;
- jedna řádka indikátorů (ikona + číslo, `title` s popisem): pipeline `finished/total` (+ selhání),
  lease (agent + zbývající čas, **jeden sdílený ticker** pro celé plátno, ne `setInterval` na kartu),
  „zadání se změnilo“, commit (zkrácené SHA z `realization`), spotřeba;
- bloky jen jako řádek: číslo, titulek, tečka stavu (`met`/`unmet`/`blocked`) a **React Flow handle portů**
  (vazby musí dál fungovat, `data-block-id` zůstává kvůli kliknutí na blok);
- porty karty (`CardPorts`) beze změny.

Na kartě NESMÍ být: `EvidenceEditor`, `CardEvidence` se seznamem běhů, `SourceRealization`, `CardRules`,
`InheritedRules`, `CardFacts`, `CardChecks` editor, textarea bloků, `PortDecisionEditor`, `PortSpawnEditor`,
`SpecificationDiff`, `WorkDetails` se seznamem souborů. Vše se přesune do popupu. Kompaktní karta
je stejná pro vybranou i nevybranou kartu i pro hromadný výběr (`Board.tsx` `isSelected`).

## 2. Popup „DNA karty“

Otevření: klik na kartu (mimo `[data-block-id]` a handle). Dvojklik dál vstupuje dovnitř.
Esc / křížek zavře a **odmountuje** obsah. Nativní `<dialog>` + `showModal()` podle
`frontend/ui-kit/removal-dialog/components/RemovalDialog.tsx`; záložky ARIA tablist podle
`editor/node-detail/components/NodeTabs.tsx`. Data záložky se načtou až při jejím otevření (lazy),
velké seznamy stránkovaně (`/agent-results?before=`).

Záložky (pořadí = pořadí orientace člověka):

1. **Přehled** – cíl, stav, kdo na kartě pracuje, a hlavně **„Co po tobě chci“**: položky kontrolního pásu
   ve stavu `no`/`run` s `hint` a tlačítkem, které otevře správnou záložku (např. „kontroly → Důkazy
   a kontroly“), `loop.waitingOnHuman`, návrh uzavření (`ConfirmProposal`), další krok pipeline.
2. **Zadání** – spec (goal / non_goals / acceptance) s revizí a historií (`/api/node-spec/history`),
   text karty, bloky s podmínkami a porty, pravidla (vlastní + zděděná s původem), rozhodnutí.
3. **Proces** – časová osa (chronologicky) z: snímků zadání (assignment), převzetí (lease), etap pipeline
   s poznámkami, výstupů agentů (`resultHistory` / `agent-results`), zpráv na vazbách, rozhodnutí,
   běhů kontrol (`checksRun.at`), realizace (commit). Filtr podle sémantické skupiny:
   Zadání · Práce · Ověření · Předávky · Kód.
4. **Pipeline a workflow** – etapy (`PipelineStageRow`) s `note`, opakování (`retryOf`) a smyčky oprav,
   bloky s porty a `onMet`, vazby na předchůdce a následníky.
5. **Důkazy a kontroly** – `checks` karty (editor `ChecksEditor` – tady člověk nastavuje kontroly),
   `evidence` tests / review / merge s odkazy, tabulka `checksRun` (jen čtení; `EvidenceEditor` až
   po tlačítku „Upravit důkazy“).
6. **Kód a verze** – `sourceRef` + `source-status`, realizace (commit → odkaz na GitHub, `prUrl`,
   `verifiedAt`), formulář realizace, OporaHub (`/api/sync-report`: synced / app-ahead / repo-ahead…),
   „zadání vs. výstup“ (`assignment-status`, porovnání `SpecificationDiff`), návrh (`design`),
   scénář E2E a poslední běh („výstup funguje v prohlížeči“).
7. **DNA** – tlačítko „Kopírovat DNA karty“: Markdown balík pro LLM, ze kterého jde kartu postavit
   znovu: `node-brief` (zadání, pravidla, bloky, upstream), pipeline s poznámkami, historie výstupů,
   důkazy, rozhodnutí, realizace (commit + cesta). Logika skládání v `logic/` s testem.

## 3. Výkon (prohlížeč nesmí padat)

- `Board.tsx`: data karty stabilní mezi polly (memo podle obsahu, ne nový objekt při každém pollu);
  `memo(NodeCard)` musí reálně držet – test na `card-model` / porovnání.
- `<ReactFlow onlyRenderVisibleElements>`.
- Jeden ticker pro lease všech karet.
- Žádný `JSON.stringify` velkých struktur při renderu karty.
- Popup jen jeden (pro otevřenou kartu), obsah se při zavření odmountuje.

## 4. Pravidla

`CLAUDE.md` a `docs/pravidla-struktury.md`: feature složka (`components/`, `logic/`, `styles/`, `README.md`),
BEM CSS s příběhovým komentářem, soubor ≤ ~200 řádků, rodič ukládá (dílek hlásí callbackem), testy
`.test.ts` vedle (`renderToStaticMarkup`), logika bez Reactu v `logic/` s testem. Nové dílky:
`frontend/editor/card-dna/` (popup, záložky, časová osa, DNA export). Kontrakt karty pro agenty
(`docs/karta-pro-agenty.md`) se nemění.

## 5. Hotovo, když (GOAL)

- `npm test` zelené, včetně nových testů:
  - kompaktní karta s 200 `checksRun`, 8 bloky po 8 portech a vybraným stavem nemá v markupu
    žádný `<input>`, `<textarea>` ani `<select>`;
  - popup má 7 záložek a obsah jen aktivní záložky;
  - časová osa řadí položky chronologicky a filtruje podle skupiny;
  - DNA export obsahuje zadání, pipeline s poznámkami, důkazy, commit a cestu.
- `npm run build` zelené.
- `uv run pytest backend` – žádný nový pád (výchozí stav: 2 padající testy graphify závislé na prostředí).
- Vše, co karta dřív ukazovala, je v popupu dosažitelné (žádná funkce se neztratí).

## 6. Dokončení implementace (2026-10-08)

- Esc, křížek, změna záložky včetně klávesnice a skrytí důkazů používají jeden
  `draft-guard`: načte dirty/pending participanty stejného project/workspace,
  vyčká `flushSaveScope` a znovu ověří čistotu. Existující flush participantů dál
  používá `confirmSavedChange`. Editor označený jako blocked se neodmountuje;
  dialog ukáže důvod a člověk zvolí Uložit/Zrušit v původním formuláři. Chyba
  ukládání ponechá koncept i aktuální panel. Souběžné přechody se neskládají.
- Rozlišení klik/dvojklik nemá pevný časovač. První click ukáže nativní
  neinteraktivní `show()` náhled (`inert`, pointer-events:none), aby původní
  karta zůstala cílem dalšího clicku. `detail === 2` náhled odmountuje a vstoupí
  dovnitř; `dblclick` už akci neopakuje. Po přesunu ukazatele mimo původní kartu
  nebo interakci klávesnicí se tentýž dialog převede na `showModal()`. Esc funguje
  i v náhledu. To řeší konflikt okamžitého showModal s doručením druhého clicku,
  aniž by aplikace hádala OS interval. Bloky, porty, handles a ovládací prvky
  tuto cestu neotevírají; modifikátory zůstávají pro výběr.
- Přehled zachovává release lease, Zadání/Pipeline decision a spawn, Zadání rename.
  Shared ticker ovládá jen odpočet, nikoli claim/heartbeat/release či jejich polling.
- Kód dostává známý source-status i všechny stavy assignment z Boardu. Externí
  odkazy jsou jen HTTPS. Historie stránkuje výsledky i zprávy; export zachová
  zprávy a celý node-brief. Chybějící hodnoty se nevydávají za ověření ani undefined.
- Feature má jediný styles/card-dna.css s BEM třídami a tokeny. Kompaktní porty
  neřežou svůj handle; oříznutý je pouze dlouhý popisek.
- Oprava přejímky A1: plánovaná prázdná cesta má stav `unspecified` / „cesta neurčena“,
  nikoli úspěch podle existence kořenové složky. UI odmítne i starou odpověď `present`.
- Oprava přejímky A2: obnoveny původní skripty `test: vitest run` a
  `build: tsc --noEmit && vite build && node tools/copy-drawing-assets.mjs`.
  Oba byly spuštěny v tomto worktree bez přepisu shellu / configLoader workaroundu.

### Dosud neověřeno v prohlížeči

Skutečný pomalý dvojklik a náhled→modalita, Esc/křížek/změna tabu/skrytí se všemi
rozepsanými editory, návrat focusu, release lease proti živému serveru,
rozhodnutí/spawn/rename, port drag-to-connect a výkon při hromadném výběru.
Jednotkové a SSR testy nejsou náhradou těchto browser kontrol.

## Výkon – měření

### Příčina a oprava (2026-10-08)

Prokázáno časovanými zámky na **8791**, data výhradně `.data/kopie`:
`backend/editor/canvas_versions/canvas_versions.py:106–115` v revizi `7e1ab39`.
`CanvasVersions.list` držel `graph_lock` a `canvas.lock` přes `SELECT * / fetchall`
(řádky 111–112) a dekódování všech snapshotů v `_summary` (řádek 113, funkce 48–54).
Nejde o prokázaný problém synchronního IO přímo v event loopu: konkrétní důkaz je
blokování ostatních vláken na společných zámcích.

- Původní uložený profil `.data/versions-before.prof`: celkem 2 820 ms,
  `fetchall` 1 833 ms, `_summary` 837 ms. Pozdější profil s konfliktní instrumentací
  není použit jako důkaz.
- Čerstvý lokální harness `.data/timed_server.py` na stejném portu zavolal původní
  **jen metodu list** načtenou pomocí `git show 7e1ab39:…`, bez přepisování/stashování
  worktree. Zámek historie držel 3 355,6 ms; souběžní čtenáři na zámek čekali
  3 240–3 305 ms. Důkaz: `.data/lock-measurements.jsonl`.
- Nová metoda: samostatné read-only SQLite spojení a dekódování mimo společné zámky,
  `backend/editor/canvas_versions/version_read_cache.py:43–51`; pod zámkem pouze
  validace rozsahu, revizí a konzistentní capture. Nejdelší naměřený úsek nové historie
  pod společným zámkem 117,1 ms. Při souběžné změně se výsledek zahodí a načte znovu.
- `backend/canvas/read_cache.py:42–59`: revize SQL (`total_changes`, `data_version`),
  bypass rozpracovaných transakcí a Git pohledů, klíče project/workspace. `get/put`
  mají vlastní RLock a kopírují vstup i výstup. Historie navíc kontroluje otisky
  materiálů; dočasné busy/IO závody mají omezený retry.
- Frontend deduplikuje rozpracované GET podle celé URL, vrací oddělené kopie,
  sdílí pollery a pozastavuje je ve skrytém okně. Zápis ruší deduplikační generaci.
  Desktop stav zachovává identitu podle revize; sync-report se načítá až pro Hub
  nebo příslušný detail, nikoli při prvním vykreslení plátna.

### Před / po

Jednotlivé vzorky, nikoli percentily nebo garantované SLA. `Před 8740` je převzato
z přejímky koordinátora; 8740 nebyl v tomto kole měněn. **Úplné srovnatelné „před“
na 8791 se stashnutými změnami nemáme.** Izolovaný replay staré metody níže není
baseline celé aplikace. Staré soubory pojmenované `before` nejsou bez doloženého
stavu zdrojů považovány za takovou baseline.

| Scénář | Před 8740, přejímka (ms) | Po 8791, mezivýsledek (ms) | Po 8791, finální build (ms) |
|---|---:|---:|---:|
| desktop-v3/leases | 5 374 | 6,2 | 4,7 |
| desktop-v3/state | 2 655 | 24,3 | 17,4 |
| bootstrap | 3 832 | 6,2 | 2,5 |
| první karty sektoru 2 | 11 700 | 407 | 421,3 |

Finální měření: Chrome headless, nový browser context, produkční build, ample,
sektor `a8257274-56e3-464f-8d92-d60d777888eb`, první `.node-card` + dva animation frames.
API vzorky jsou následná dokončená čtení včetně těla (zahřáté cache); nelze je
zaměnit za latenci všech souběžných požadavků při startu. Síťový záznam neobsahuje
sync-report. Artefakt `.data/browser-verified.json`, skript `.data/browser_measure.py`.

Izolovaný souběh na 8791 (`.data/final-contention.json`; historie a další požadavky
spuštěné po 50 ms, stejné kopie dat, měřicí instrumentace + běžná souběžná zátěž):

| HTTP požadavek | Stará metoda list (ms) | Nová studená historie (ms) | Nová zahřátá historie (ms) |
|---|---:|---:|---:|
| historie (114 verzí) | 3 625,5 | 3 785,3 | 15,3 |
| souběžné leases | 3 581,3 | 367,4 | 29,8 |
| souběžný bootstrap | 3 573,7 | 231,6 | 4,4 |
| souběžný state | 3 609,6 | 366,4 | 28,9 |

Studená historie zůstává nákladná; oprava odstraňuje hlavně blokování ostatních
požadavků a opakované dekódování. Metadata starých verzí se nemigrovala. Artefakty
měření a kopie databází zůstávají mimo commit pod existujícím `.gitignore: .data/`.

### Audit všech zápisových cest

`backend/canvas/test_cache_write_paths.py::test_write_reads_fresh_value_with_warm_cache`
obsahuje **18 parametrů**. Každý skutečně zavolá HTTP handler → produkční zápisovou
službu. Před zápisem zahřeje view/state/settings/versions a relevantní další čtení,
po zápisu ověří nový obsah a shodu s nezávislým čtením při vypnutém `ReadCache.get`.
Původní doménové aserce scénáře zůstávají zachovány. Úspěšná odpověď bez změny dat
sama o sobě nestačí; každý parametr musí mít alespoň jeden měnící zápis.

| Parametr / cesta | Zápisová hranice / invalidace |
|---|---|
| state | DesktopV3State.save → desktop_v3_state |
| graph | CanvasService.save_graph → drafts; Git pohled je bez cache |
| node-spec | NodeSpecStore.save → node_spec_revisions |
| node-text | NodeTextStore.access → node_text_revisions |
| canvas-plan | apply_plan → graf, texty, specifikace, desktop stav v transakci |
| pipeline | pipeline route/add → DesktopV3State.save |
| lease | CardLeases.apply → card_leases, assignment snapshot, work activity |
| agent-output | AgentOutput.apply → desktop stav a historie výsledků |
| agent-workspace | AgentWorkspace.save → agent_workspace_revisions |
| block | BlockAccess.apply → DesktopV3State.save |
| rule | MemoryItems.apply → změna pravidla v desktop stavu |
| decision | MemoryItems.apply → změna rozhodnutí v desktop stavu |
| realize-source | realize_source → save_graph, nový sourceRef + realization |
| versions-save | CanvasVersions.save → canvas_versions |
| versions-restore | CanvasVersions.restore → graf, stav, obsah, soubory; nová SQL generace + otisky souborů |
| settings | ProjectHub.save_settings → registr + project_settings/profile |
| import-project | ProjectHub.local_project → registr + nový projektový draft; opakované připojení je idempotentní |
| remove-project | Removals.remove → archivace registru; zahřátý scope následně odmítne čtení |

Každý SQL zápis konzervativně invaliduje projektovou generaci; registry zápisy
navíc generaci registru. Nemusíme ručně udržovat seznam invalidate callbacků v každém
writeru. Git connect/import/sync používají register_repository a zápisy registru;
Git HEAD/index/pracovní soubor se necachují. Síťový clone nebyl v tomto kole spouštěn.
Import v parametrizovaném testu znamená připojení existujícího lokálního projektu.

Další testy: dva projekty a dva workspace se stejnými datovými klíči; odmítnutí
neplatného veřejného scope; commit druhého SQLite spojení; read-your-write uvnitř
transakce a rollback; mutace vrácené kopie; deterministický souběh get/eviction
(před zámkem reprodukoval KeyError, po opravě prošel); dekódování historie bez
společných zámků; retry po busy DB nebo změně materiálu; Git HEAD invalidace historie
sync-reportu; frontend nekříží mutovatelné výsledky mezi odběrateli.

### Závěrečné kontroly

- `npm test`: 1 064 passed / 153 souborů. Včetně obou testů CardDnaCode a nového
  případu plánované prázdné cesty se starou odpovědí present.
- `npm run build`: prošel (`tsc --noEmit`, Vite, kopie fontů). Varování o velkých
  chunkech zůstává. `npm config get script-shell` = null; žádný lokální workaround.
- Cílená cache sada: 30 passed (18 zápisových cest + 12 scope/cache/souběh/retry).
- Nezávislé read-only review finálního diffu: bez konkrétního bezpečnostního nebo
  logického blockeru. Diagnostický harness není součástí produkčního kódu.
- Finální `uv run pytest backend`: **1 458 passed, 4 skipped, 2 failed**, 2 warnings,
  532,87 s. Pouze známé environmentální Graphify chyby:
  `backend/api/project/test_graphify_routes.py::test_generate_uses_official_graphify_and_persists_output`
  a `backend/project/maps/test_map_refresh.py::test_real_graphify_refresh_publishes_only_selected_project`.
  Příčina obou: chybí `graphifyy==0.9.24` / nastavení `OPORA_GRAPHIFY_PYTHON`.
  První průběžný běh měl navíc chybu inicializace databáze v novém testu scope;
  po opravě fixture byl celý původní příkaz spuštěn znovu. Hash kontrola všech
  1 143 zdrojových/testovacích souborů potvrdila během finálního běhu nulový drift.
- Server 8791: po měření čistý shutdown aplikace, exit 0 a ověřené odmítnutí TCP
  spojení. Oba vlastní pytest procesy skončily. Vite v tomto kole nebyl spuštěn;
  existující preview koordinátora na 5199 nebylo měněno ani ukončováno.
