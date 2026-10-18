# Výkon plátna při velkých datech: měření a plán oprav

Datum: 2026-10-14 · Stav: návrh (jen čtení kódu a měření, nic se neměnilo)

Uživatel hlásí, že plátna a karty se „sekají“, když je dat hodně, a že velká plátna „padají“. Tenhle dokument
popisuje, kudy se plátno vykresluje, co přestavbu spouští, co se naměřilo na syntetickém grafu (300 až 3000
karet) a jaké opravy pomůžou nejvíc za nejmenší práci.

Navazuje na backendové karty P1 až P3 (`8f19fb9` poller bez zahlcení, `4bdec60` zámky po projektech a WAL,
`b5988c1` cache podle revize, ETag/304 a štíhlé zápisy). Ty řešily I/O a souběh. Tady jde o
**výpočet a vykreslení v prohlížeči** a o **odvozené endpointy, které rostou kvadraticky**.

---

## 1. Shrnutí

Sekání má tři příčiny, které se navzájem násobí:

1. **Board při každé přestavbě přepočítá všechno pro všechny karty a některé výpočty rostou s N².** Na 2000
   kartách trvá jen datová část přestavby uzlů asi 260 ms a výpočet hran dalších 254 ms. Hrany se navíc
   počítají při **každém** renderu Boardu, tedy i v každém snímku tažení karty a každých 2,5 s kvůli pollingu
   `bootstrap` v App.
2. **`React.memo` na kartě nic nechrání.** `make()` staví pro každou kartu nový objekt `data` a zhruba 20
   nových closures, takže každá přestavba překreslí všech N karet. Karta navíc vykresluje editory všech portů
   všech bloků (select, textarea, details), i když vybraná není: asi 164 elementů a 15 kB HTML na kartu, ve
   2000 kartách tedy kolem 330 000 DOM uzlů. `onlyRenderVisibleElements` se nikde nepoužívá.
3. **Přestavbu spouští skoro všechno.** Idle polling (leases 10 s, frontier, work a scenario po 15 s,
   assignment a source po 30 s) vrací pokaždé nový objekt, i když se data nezměnila. To dává asi
   **22 úplných přestaveb za minutu bez jediné akce uživatele**. Každá editace (`desktop.mutate`) nebo
   tažení navíc spustí 4 až 6 dalších dotazů a každá odpověď znovu přestaví celé plátno.

K „padání“ velkých pláten vedou dvě cesty:

- **Zápis stavu narazí na strop 2 MB.** `desktop.mutate` posílá při každé změně celý stav. Na 1600 kartách po
  3 blocích má stav 2258 kB a server vrátí **413 „Požadavek je příliš velký“**, takže od té velikosti selže
  každá úprava bloku. Strop je v `backend/app/factory.py:165`. K tomu jsou pevné stropy grafu 2000 uzlů a
  4000 vazeb (`backend/canvas/graph.py:137`) a stavu 2000 uzlů (`backend/editor/agent_memory/desktop_v3_state.py:36`).
- **Backendové odvozené endpointy rostou kvadraticky.** Na 1600 kartách trvá `frontier` 1,64 s,
  `work-overview` 1,56 s a `card-checklist` 0,54 s. Běží v jednom procesu pod GIL a po každé editaci se
  volají všechny najednou.

---

## 2. Kudy se plátno vykresluje

| Krok | Kde | Poznámka |
|---|---|---|
| App drží graf (`view.graph`), stav (`useDesktopState`), leases, usage, assignment a source status | `frontend/app/components/App.tsx:234-237, 295` | App má 1798 řádků. Každý jeho render překreslí i Board, protože Board není `memo` a dostává inline callbacky. |
| Polling `bootstrap` každých 2,5 s | `App.tsx:363-367`, `bootstrap()` na `:309-316` | `setProjects`, `setDraftProject` a `setJobs` nastaví pokaždé nová pole, takže App i Board se překreslí každých 2,5 s. |
| `useSaveScope` v App | `App.tsx:530` → `frontend/shared/hooks/logic/save-coordinator.ts:50-53` | Při každém renderu App projde `saveScopeEntries` všechny participanty a zavolá `isDirty`. U každé karty je to `CardBlocks.hasDraft()`, tedy `querySelectorAll` nad DOM karty (`CardBlocks.tsx:40-44`). |
| Board: polling overlayů | `frontend/editor/canvas/board/components/Board.tsx:231-243` | `useFrontier` (15 s + při změně `state`), `useCardChecklist` (20 s + `state`), `useWorkOverview` a `useScenarioHistory` (15 s + `{graph,state}`), `useBriefVault`. |
| `make()` postaví všechny uzly vrstvy | `Board.tsx:244-351` | Pro každou kartu volá `cardView`, `graph.nodes.filter` (počet dětí), `upstreamRows`, `effectiveRules`, `state.rules.filter`, `proposalCount`, `evidenceReadiness`, `resolveFacts`, `movedCards.includes` a `multiSelected.includes` a k tomu vyrábí asi 20 closures. |
| Přestavba uzlů v efektu se 22 závislostmi | `Board.tsx:361-369` | Přenáší `measured`, `width` a `height` ze starých uzlů (paměťová poznámka: bez toho karty ztratí fokus). Chybí v nich `checklists` a `vaultIndex`, takže pás a čipy schránky se ukážou až s jinou změnou (drobná chyba). |
| Hrany | `Board.tsx:443-456` a `:515` | Počítají se v těle renderu bez `useMemo`. Pro každou hranu volá `handoffMark`, která pokaždé staví `new Map` ze **všech uzlů grafu** (`card-checklist.ts:54`), tedy O(E·N). Na `:515` se pak všechny hrany ještě jednou kopírují kvůli `selected`. |
| `onNodesChange` | `Board.tsx:374-381` | Každý snímek tažení zavolá `setNodes`, Board se překreslí a s ním se přepočítají i hrany (předchozí řádek). |
| `useAddedPulse` | `frontend/editor/canvas/node-card/logic/use-added-pulse.ts:3-14` | Při každém renderu `JSON.stringify` všech pozic, `addedIds` je O(n²) přes `includes`. |
| `ReactFlow` | `Board.tsx:511-626` | `nodeTypes` je stabilní (modul, `:58`), dobře. Chybí `onlyRenderVisibleElements`. Hrany typu `smoothstep`. `MiniMap` s funkcí `nodeColor` pro všechny uzly. |
| Karta | `frontend/editor/canvas/node-card/components/NodeCard.tsx:75-125` | `memo` bez vlastní rovnosti. `CardBlocks` → `CardBlockPorts` vykreslí u každého portu tlačítko, odebrání, `<details>` se `<select>` a `<textarea>`, druhý `<details>` s checkboxem a `Handle`. U 3 bloků po 2 portech je to 12 handle a 164 elementů na kartu. |
| Bloky vedle karet | `App.tsx:610-613` → `buildBlockNodes` | Memo je v pořádku a výpočet levný (0,6 až 1,2 ms). |

### Co spouští úplnou přestavbu (všech N karet)

| Spouštěč | Frekvence | Důsledek |
|---|---|---|
| Polling leases, frontier, work, scenario, assignment, source (nový objekt i při stejných datech) | asi 22× za minutu v klidu | `make()` + render všech karet |
| `desktop.mutate` (úprava textu bloku, port, důkaz…) | každá editace | optimistický `setState`, pak `setState(value.state)` ze serveru, k tomu refetch frontier, checklist, work, scenario, usage a assignment. Celkem **6 až 8 přestaveb** a na serveru asi 1,3 s CPU (1000 karet) až 3,8 s (1600 karet). |
| Tažení karty (onDragStop → `save({...graph})`) | každé puštění | POST celého grafu (566 kB při 1600 kartách), nový `graph`, přestavba a refetch frontier, checklist, work a scenario |
| Klik na kartu (změna `selected`) | každý výběr | úplná přestavba |
| Render App (bootstrap 2,5 s, každá změna stavu App) | ≥ 24× za minutu | přepočet hran O(E·N) a kopie všech hran |
| Snímek tažení | asi 60× za sekundu | přepočet hran O(E·N) a `setNodes` |

---

## 3. Měření

Skripty leží mimo repo v `C:\Users\Admin\AppData\Local\Temp\claude\perf-scratch\` (junction na
`node_modules` repa, vitest s aliasem `@` na `frontend/`, backend přes `uv run python`):

- `synthetic.ts` / `bench_backend.py`: syntetický graf. L karet v jedné vrstvě, z toho L/50 sektorů s 10 dětmi
  o vrstvu níž. Každá karta má 3 bloky po 2 portech, každá 3. má pravidlo a každá 5. rozhodnutí a návrh
  uzavření. Třetina vazeb je z portu bloku, čtvrtina vazeb má zprávu.
- `board.perf.test.ts`: čisté funkce, které Board volá při přestavbě (medián ze 3 po zahřátí).
- `render.perf.test.tsx`: `renderToString` N karet `NodeCard` v `ReactFlowProvider`. Je to **dolní mez**:
  bez DOM, bez commitu, bez obalu `NodeWrapper` z React Flow, bez ResizeObserveru a měření handle.
- `profile_backend.py`: cProfile odvozených funkcí backendu.

Stroj: vývojový Windows 11 notebook, Node + vitest 3.2.4, Python 3.12.

### 3.1 Datová část přestavby Boardu (ms na jednu přestavbu)

| L karet / E vazeb | cardView + počet dětí | upstreamRows | effectiveRules | sectorViews | proposalCount | movedCards.includes | **hrany (handoffMark)** | addedIds (1 posun) |
|---|---|---|---|---|---|---|---|---|
| 300 / 450 | 1,7 | 2,3 | 3,7 | 0,2 | 0,4 | 0,3 | **6,1** | 0,3 |
| 1000 / 1500 | 6,4 | 13,0 | 41,7 | 1,4 | 0,7 | 4,5 | **61,1** | 4,8 |
| 2000 / 3000 | 13,3 | 43,7 | **174,4** | 7,2 | 3,4 | 16,0 | **254,1** | 16,5 |
| 3000 / 3000 | 34,0 | 64,2 | **358,5** | 15,5 | 6,2 | 34,5 | **361,1** | 34,7 |

Součet `make()` je asi 70 ms (1000), 260 ms (2000) a 520 ms (3000). K tomu hrany 61, 254 a 361 ms **při každém
renderu Boardu**.

Stejné výsledky přes jednorázové indexy (`byId`, počty dětí, příchozí hrany podle cíle, rozhodnutí podle uzlu,
pravidla podle cíle, mapa druhů pro hrany) zabraly **0,7 / 3,2 / 6,1 / 8,8 ms**. Pro 2000 a 3000 karet je to
zrychlení 80× až 100×.

Zbytek je zanedbatelný: `buildBlockNodes` do 1,2 ms, `layerFootprints` při puštění karty do 0,8 ms,
`JSON.stringify` otisku schránky do 1 ms.

### 3.2 Render karet (React, `renderToString`, bez DOM)

| L karet | dev build ms (ms/kartu) | **production build ms (ms/kartu)** | HTML |
|---|---|---|---|
| 300 | 222 (0,74) | – | 4,6 MB |
| 1000 | 930 (0,93) | **325 (0,33)** | 15,2 MB |
| 2000 | 1683 (0,84) | **618 (0,31)** | 30,5 MB |
| 3000 | 2548 (0,85) | – | 45,8 MB |
| 2000, **karty bez řádků bloků** (odhad LOD) | – | **127 (0,06)** | 6,7 MB |

Jedna nevybraná karta má 15,4 kB HTML, 164 elementů a 12 handle. Asi **80 % času renderu karty připadá na
podstrom bloků a portů**, hlavně na editory portů, které jsou vidět jen po rozbalení.

Realisticky tedy jedna úplná přestavba na 2000 kartách stojí ≥ 260 ms dat + ≥ 620 ms Reactu, a pak commit,
layout a paint 330 000 DOM uzlů. Při asi 22 přestavbách za minutu v klidu to vychází na **≥ 30 % hlavního
vlákna jen na polling**. To je odvozeno z naměřených částí, v prohlížeči to ještě potvrďte podle kroků v §6.

### 3.3 Backend (TestClient, čerstvá data v tmp, teplý medián ze 4)

| Endpoint | 300 karet | 1000 karet | 1600 karet (1920 uzlů, 3000 vazeb) | Velikost (1600) |
|---|---|---|---|---|
| GET `/api/view` | 1,4 ms | 2,6 ms | 3,9 ms (304: 0,9 ms) | 473 kB |
| GET `/api/desktop-v3/state` | 3,2 ms | 10,2 ms | – (stav kvůli 413 neuložen) | 1267 kB při 1000 |
| GET `/api/desktop-v3/card-checklist` | 33 ms | 195 ms | **545 ms** | **1540 kB** |
| GET `/api/desktop-v3/frontier` | 56 ms | 521 ms | **1638 ms** | 504 kB |
| GET `/api/desktop-v3/work-overview` | 47 ms | 499 ms | **1557 ms** | 380 kB |
| GET `/api/desktop-v3/node-brief` | 16 ms | 42 ms | 69 ms (studený 214) | 493 kB |
| GET usage-summary, leases, scenario, assignment, source, brief-vault | ≤ 3 ms | ≤ 8 ms | ≤ 12 ms | – |
| POST `/api/graph` (celý graf, i po posunu 1 karty) | 14 ms | 38 ms | 76 ms | tělo 566 kB, odpověď 473 kB |
| POST `/api/desktop-v3/state` (celý stav) | 70 ms | 375 ms | **413 Request too large** (2258 kB > 2 MB) | – |

Profil při 1000 kartách (cProfile):

- `frontier` 344 ms. 1000× volá `sector_blockers` (`backend/editor/agent_packet/sector_status.py:40-61`),
  který **při každém volání** staví `by_id` ze všech uzlů a prochází všechny hrany. To je 6 milionů
  `dict.get`. K tomu `frontier.py:55-56` prochází všechny hrany pro každou kartu.
- `work_overview` 493 ms. Volá `frontier` pro **každého rodiče** (21×, `work_overview.py:22-23`) a pak
  počítá sektory přes průchod předky O(S·N·hloubka) (`:39-50`).
- `checklists` 146 ms. `card_items` prochází všechny hrany dvakrát pro každou kartu (`card_checklist.py:28-29`)
  a čte specifikaci a text po jednom dotazu na kartu (2000 SQL, `:93-94`).
- Route `/frontier` navíc pro všechny řádky spočítá i `checklists` (`backend/api/editor/desktop_v3_routes.py:120-123`),
  takže frontier v UI platí za oba výpočty najednou.

---

## 4. Hlavní úzká hrdla (seřazeno podle dopadu)

1. **Hrany se přepočítávají v každém renderu a mají O(E·N)**: `Board.tsx:451-456`, `card-checklist.ts:54`.
   Stojí 254 ms při 2000 kartách na každý snímek tažení a každé 2,5 s.
2. **Kvadratické výpočty v `make()`**: `effective-rules.ts:8` (Map ze všech uzlů pro každou kartu),
   `upstream.ts:5-6`, `Board.tsx:283` (počet dětí přes `filter`), `Board.tsx:301` (`includes`),
   `sector-status.ts:20-28` a `completion-proposals.ts:9-11`. Dohromady 260 ms při 2000 kartách.
3. **Nestabilní `data` karet**: `Board.tsx:290-349`. `memo` na `NodeCard.tsx:75` kvůli tomu nefunguje
   a každá přestavba znamená render všech karet (≥ 620 ms při 2000 kartách).
4. **Těžká nevybraná karta**: `CardBlockPorts.tsx` vykresluje editory portů vždy. 80 % renderu a 15 kB DOM
   na kartu.
5. **Žádná virtualizace**: chybí `onlyRenderVisibleElements` a v DOM jsou všechny karty a hrany.
6. **Polling vrací nové objekty i bez změny a revize spouští dávky refetchů**: `use-frontier.ts:20`,
   `use-work-overview.ts:14`, `use-leases.ts:12`, `use-scenario-history.ts:12` a další. To dělá asi 22
   přestaveb za minutu v klidu a 6 až 8 po každé editaci.
7. **Kvadratické odvozené endpointy na backendu**: `sector_status.py:40`, `frontier.py:55`,
   `work_overview.py:22`, `card_checklist.py:28` a N+1 SQL. 1,6 s na volání při 1600 kartách a po
   každé editaci se volají současně.
8. **Zápisy celého stavu a celého grafu**: `state-store.ts:108-140` posílá a přijímá celý stav (1,4 MB
   při 1000 kartách, 375 ms). Od zhruba 1500 karet s bloky dostává **413** (strop 2 MB v `factory.py:165`).
   Posun jedné karty posílá celý graf (`App.tsx` `onPosition`).
9. **Překreslování App**: `bootstrap` každých 2,5 s bez porovnání a `useSaveScope` s `querySelectorAll`
   pro každou kartu. To se bez prohlížeče změřit nedalo, dopad roste lineárně s N.
10. **Menší položky**: `MiniMap` nad tisíci uzly, hrany `smoothstep` se štítky „✉“ (měření `getBBox`),
    nekonečná animace `box-shadow` (`node-card.css:392-398`), `filter` na uzavřených a blokovaných kartách
    (`:33`, `:385`, `:388`) a `addedIds` O(n²).

---

## 5. Plán oprav

Pořadí bere zisk ku práci a riziku. Opravy 1, 2 a 7 jsou čisté funkce s testy, takže jdou nasadit hned a
bez rizika pro chování. Opravy 3 až 5 mění React vrstvu a je potřeba u nich hlídat přenos `measured`
(fokus v kartách).

### Oprava 1: Hrany v `useMemo` a `handoffMark` bez Map pro každou hranu (S, nízké riziko)

- **Soubory:** `frontend/editor/canvas/board/components/Board.tsx:443-456, 515`,
  `frontend/editor/canvas/card-checklist/logic/card-checklist.ts:51-59` (+ test).
- **Co:** `handoffMark(edge, state, kinds: Map)` dostane hotovou mapu druhů, mapa se postaví jednou za výpočet.
  Pole hran do `useMemo([graph, state, blocks.edges, addedEdges, selectedEdge])` a `selected` přímo v něm,
  aby nevznikla druhá kopie na `:515`. Stejně tak `ids`, `commentIds` a `areaIds` do `useMemo`.
- **Zisk:** hrany 254 → asi 2 ms (2000 karet) a 361 → asi 3 ms (3000 karet). Tažení přestane počítat hrany
  v každém snímku a render App každých 2,5 s bude levný.
- **Ověření:** `npm test` (`card-checklist.test.ts`). V benchi `board.perf.test.ts` sloupec `edges` pod 5 ms.
  V React Profileru při tažení karty ve 2000kartovém projektu commit Boardu pod 16 ms.

### Oprava 2: Jednorázový index vrstvy pro `make()` (M, nízké riziko)

- **Soubory:** nový `frontend/editor/canvas/board/logic/board-index.ts` + `board-index.test.ts`.
  Volitelný parametr indexu do `upstream.ts`, `effective-rules.ts`, `sector-status.ts` a
  `completion-proposals.ts` (staré podpisy zůstanou pro inspektor). `Board.tsx:244-351`.
- **Co:** jednou za přestavbu postavit `byId`, `childrenCount`, `incomingByTarget` (bez `flow`),
  `decisionsByNode` (+ množinu nahrazených), `nodeRulesByTarget`, `proposalsBySector` (jeden průchod stromem),
  `sectorMembers` (jeden průchod předky s memoizací) a místo `movedCards` a `multiSelected` použít `Set`.
  `useMemo([graph, state])` pro index, aby změna výběru index nepřestavovala.
- **Zisk:** datová část přestavby 260 → asi 6 ms (2000) a 520 → asi 9 ms (3000), změřeno na indexované
  variantě v benchi.
- **Riziko:** nízké. Výstupy jsou stejné, ověří je test, který porovná indexovanou a původní variantu na
  syntetickém grafu.
- **Ověření:** `npm test` a bench (sloupce cardView až movedIncludes dohromady pod 10 ms při 2000 kartách).

### Oprava 3: Stabilní `data` karet, aby `memo` platilo (M až L, střední riziko)

- **Soubory:** `Board.tsx:244-369`, `NodeCard.tsx` a nový `frontend/editor/canvas/board/logic/board-actions.ts`
  (+ test čisté části).
- **Co:**
  - Callbacky karet (`rename`, `blocks.*`, `ports.toggle`, `saveEvidence`, `completion.confirm`…) přestanou
    být closures pro každý uzel. Board předá jeden stabilní objekt akcí přes kontext (ref na poslední
    props, `useRef` + `useMemo([])`), karta volá `actions.cardBlock(id, event)`.
  - Přestavba uzlů pak porovná nová `data` s předchozími (mělká rovnost hodnotových polí, u odvozených polí
    rovnost reference ze stabilního indexu). Když se karta nezměnila, **vrátí předchozí objekt uzlu** (se
    zachovaným `measured`) a React Flow i `memo` ji přeskočí.
  - Do závislostí doplnit `checklists` a `vaultIndex` (dnešní chybu tím opravíme).
- **Zisk:** výběr karty překreslí 2 karty místo N. Odpověď pollingu překreslí jen karty, kterým se změnila
  data. Render 620 ms → jednotky ms u běžných změn (2000 karet).
- **Riziko:** zastaralé closures (řeší ref s posledními props) a přenos `measured` (paměťová poznámka:
  znovupoužitý objekt uzlu `measured` nese, nově postavený ho musí dostat jako dnes na `Board.tsx:362-367`).
- **Ověření:** React Profiler se zapnutým „Record why each component rendered“. Klik na kartu ve 2000kartovém
  projektu má překreslit ≤ 3 `NodeCard`, idle polling žádnou, pokud se data nezměnila. Ruční test: rozepsaná
  textarea v kartě neztratí fokus při změně výběru jiné karty ani při doběhnutí pollingu.

### Oprava 4: Úroveň detailu karty (M, střední riziko, rozhodnutí o UX)

- **Soubory:** `CardBlocks.tsx`, `CardBlockPorts.tsx`, `NodeCard.tsx`, `styles/node-card.css`.
- **Co:**
  - Nevybraná karta vykreslí u portu jen popisek a `Handle`. Editor rozhodnutí, spawn a tlačítko odebrání
    jen u vybrané karty (nebo po rozbalení). **`Handle` musí zůstat vždy**, jinak se hrany nemají kam
    připojit.
  - Zoom LOD: `useStore(s => s.transform[2] < 0.45)` vrací jediný boolean, takže karta se překreslí jen při
    překročení prahu. Pod prahem jen hlava, název, stav a handle (bez textarea bloků).
  - Volitelně práh podle počtu karet ve vrstvě (např. nad 400 vždy kompaktní řádky bloků).
- **Zisk:** render 618 → asi 127 ms (2000 karet, změřeno bez řádků bloků) a DOM asi 15 → 3 kB na kartu, tedy
  zhruba 75 % méně uzlů a výrazně rychlejší pan a zoom.
- **Riziko:** dnes jde psát do textarea bloku i v nevybrané kartě. Po změně stačí jeden klik na výběr navíc
  (první klik kartu stejně vybere). Rozepsaný text nesmí zmizet při přepnutí LOD: textarea se smí skrýt jen
  tehdy, když není `dirty` ani nemá fokus.
- **Ověření:** bench `render.perf.test.tsx` (varianta kompaktní). V DevTools Elements počet uzlů
  (`document.querySelectorAll('*').length`) před a po. Performance trace panu a zoomu ve 2000kartovém
  projektu, cíl ≥ 45 fps.

### Oprava 5: `onlyRenderVisibleElements` (S + úpravy, střední riziko)

- **Soubory:** `Board.tsx:511` a kvůli nezměřeným uzlům `reveal-node.ts` a `Board.tsx:413-442`.
- **Co:** zapnout `onlyRenderVisibleElements`. Upravit cesty, které čekají na `measured` u uzlu mimo
  viewport:
  - `reveal` (`Board.tsx:421`) dnes čeká až 90 snímků na `measured` a uzel mimo obraz se nikdy nezměří. Je
    potřeba použít odhad rozměru karty (`CARD_GRAB` × 2 nebo `layerFootprints(..., estimate=true)`).
  - `heightsRef` pro „Srovnat“ musí brát odhad pro nezměřené karty (`layout-model.ts` už `estimate` má).
  - Rozepsaný text v kartě, která odjede z obrazu, se odmontuje bez `blur`. Kartu, jejíž participant
    `CardBlocks` je `dirty`, je potřeba držet vykreslenou (React Flow to sám neumí), nebo commitnout draft
    při odmontování.
- **Zisk:** při přiblížení na část velkého plátna DOM úměrný viewportu (desítky karet místo tisíců). Při plném
  oddálení pomůže jen spolu s opravou 4.
- **Ověření:** ruční: reveal karty z katalogu mimo obraz, „Srovnat“ a rozepsaná textarea při posunu plátna.
  V Profileru počet `NodeCard` v commitu odpovídá viditelným kartám.

### Oprava 6: Polling bez prázdných přestaveb a sloučený overlay vrstvy (M, nízké až střední riziko)

- **Soubory:** `use-frontier.ts`, `use-work-overview.ts`, `card-checklist.ts` (`useCardChecklist`),
  `use-scenario-history.ts`, `use-leases.ts`, `use-assignment-status.ts`, `use-source-status.ts` a v App
  `bootstrap()` (`App.tsx:309-316`). Pozor: `frontend/shared/hooks/logic/poller.ts` právě upravuje jiný
  agent, sladit s ním.
- **Co:**
  - Nová data uložit jen tehdy, když se liší (porovnat surový text odpovědi nebo ETag s `If-None-Match`,
    vzor z `b5988c1`). Při shodě nechat **starou referenci**.
  - Refetch kvůli revizi (`refreshKeys: [revision]`) sloučit s debounce asi 400 ms, aby jedna editace
    znamenala jednu dávku, ne 6 samostatných přestaveb.
  - Jako `revision` předávat `desktop.revision` a `view.digest` (čísla), ne objekty `state` a `{graph,state}`
    (`Board.tsx:231-243`).
  - Krok 2: jeden endpoint `GET /api/desktop-v3/board-overlay?layer=` vrací frontier, checklist, work a
    scenario pro vrstvu najednou. Jeden dotaz, jedna přestavba a backend sdílí indexy (oprava 7).
- **Zisk:** v klidu asi 22 → 0 přestaveb za minutu, pokud se nic neděje. Po editaci 6 až 8 → 2 přestavby.
- **Ověření:** test `use-polling` / porovnání v čisté funkci (`same-response.ts` + test). V DevTools Network
  v klidu odpovědi 304 a v Profileru žádný commit Boardu mezi akcemi.

### Oprava 7: Backend: indexy místo O(N²) v odvozených pohledech (S až M, nízké riziko)

- **Soubory:** `backend/editor/agent_packet/sector_status.py`, `frontier.py`, `work_overview.py`,
  `card_checklist.py` (+ jejich `test_*.py`). Mimo právě editované `backend/canvas/*` a `backend/project/*`.
- **Co:**
  - `sector_blockers` přijme předpočítaný `by_id` a seznam hran `next` do sektorů (postavené jednou
    ve `frontier`).
  - `frontier` předpočítá příchozí `next` hrany podle cíle.
  - `work_overview` spočítá `sector_status` jednou a frontier pro všechny rodiče v jednom průchodu. Počty
    sektorů přes jednorázovou mapu předků.
  - `card_items` dostane hotové `outgoing` a `touching` podle uzlu.
  - `checklists` načte specifikace a texty jedním dotazem (`IN (...)`) místo 2N dotazů.
  - Route `/frontier` přestane počítat `checklists` pro UI, nebo je vezme z téže cache.
  - Výsledky cachovat podle datového tokenu (vzor `view` memo z `b5988c1`) a přidat ETag/304.
- **Zisk:** odhad z profilu: frontier 521 → pod 30 ms, work-overview 499 → pod 40 ms, card-checklist
  195 → asi 20 ms (1000 karet). Při 1600 kartách z 1,6 s na desítky ms. Server přestane po každé editaci
  sekat i ostatní okna a agenty.
- **Ověření:** `uv run pytest backend` (testy frontier, sector status, card checklist, work overview) a
  `bench_backend.py` ze scratch (doporučuji ho přenést do `tools/perf/bench_synthetic.py`). Cíl: všechny
  GET pod 100 ms při 1600 kartách.

### Oprava 8: Štíhlé zápisy uzlu a pozic, aby velké plátno nepadalo na 413 (M až L, střední riziko)

- **Soubory:** `frontend/shared/desktop-state/logic/state-store.ts:108-140`, `slim-writes.ts`, App
  (`onCardBlock`, `onPosition`, `onBlockMove`) a backend route v `backend/api/editor/desktop_v3_routes.py`
  + `canvas_routes.py` (koordinovat s agenty, kteří edituje `backend/canvas/*`).
- **Co:** `POST /api/desktop-v3/node` (patch jednoho `state.nodes[id]` s `expectedRevision`, odpověď jen
  revize a uzel) podle vzoru `rule` a `decision` z P3 (`appliesTo` / `withItem`). Pro tažení
  `POST /api/graph/positions` (jen `{id,x,y}` a digest). Klient vloží změnu do stavu bez nahrazení celého
  objektu, takže z oprav 2 a 3 zůstane většina karet beze změny reference.
- **Zisk:** editace bloku při 1000 kartách z 1,4 MB a 375 ms na kB a ms a **žádné 413** nad 1500 kartami.
  Tažení karty z 566 kB na desítky bajtů.
- **Riziko:** konflikty revizí. Řešit stejně jako slim writes: při skoku revize o víc než 1 načíst celý stav.
- **Ověření:** `uv run pytest backend` (nový test route + test, že starý celo-stavový zápis dál funguje),
  `npm test` (`slim-writes.test.ts` rozšířit) a bench: zápis bloku při 1600 kartách vrátí 200.
- **Navíc:** rozhodnout o stropech `len(nodes) > 2000` (`graph.py:137`) a `MAX_NODES = 2000`
  (`desktop_v3_state.py:36`). Dnes je to tvrdý strop, který UI neukazuje dopředu. Minimálně zobrazit
  varování při 80 % stropu.

### Oprava 9: Klid v App (S až M)

- `bootstrap()` (`App.tsx:309-316`): `setProjects`, `setJobs` a `setDraftProject` jen při změně (porovnání
  JSON), nebo ETag na `/api/bootstrap`.
- `CardBlocks.tsx:40-44`: `dirty` držet v refu nastaveném v `onInputCapture` místo `querySelectorAll`
  v každém renderu a v každém `isDirty`. Případně jeden participant za Board místo jednoho za kartu (dnes
  mount N karet vyvolá N× `notifySaveParticipants`).
- `Board` zabalit do `memo`, až budou callbacky z App stabilní. Do té doby stačí oprava 1, aby byl render
  Boardu levný.
- **Ověření:** React Profiler v klidu 60 s, počet commitů App ≤ 1 za minutu bez změny dat.

### Oprava 10: Drobnosti (S)

- `MiniMap` skrýt nebo zjednodušit nad asi 500 uzly (React Flow ji při každé změně uzlů překreslí).
- Hrany nad asi 1000 kusů typu `default`/`straight` místo `smoothstep` a obálku „✉“ bez `labelShowBg`
  (méně `getBBox`).
- CSS: `opora-working` animovat `opacity` pseudo-elementu místo `box-shadow` a `filter` na uzavřených
  a blokovaných kartách nahradit barvou nebo `opacity`.
- `addedIds` přes `Set` (34 ms → < 1 ms při 3000 kartách).

---

## 6. Jak ověřit v prohlížeči (React Profiler, Performance)

1. Vyrobit syntetický projekt: `bench_backend.py` ze scratch (funkce `make`) zapsat do kopie dat, nikdy ne do
   `.data/production`. Pro 1600 karet ubrat text bloků, aby stav prošel limitem 2 MB, nebo měřit až po
   opravě 8.
2. Production build (`npm run build` + backend), Chrome, React DevTools → Profiler → ⚙ „Record why each
   component rendered“.
3. Scénáře a cíle:
   - **Klid 60 s:** dnes asi 22 commitů Boardu se všemi `NodeCard`. Cíl: 0 až 2 commity, žádný s víc než 5 kartami.
   - **Klik na kartu:** dnes všech N karet. Cíl: ≤ 3 karty a commit pod 16 ms.
   - **Tažení karty 3 s** (Performance panel): FPS a délka tasků. Cíl ≥ 45 fps a žádný task nad 50 ms.
   - **Úprava textu bloku a blur:** počet commitů do ustálení a Network (počet a velikost dotazů). Cíl:
     ≤ 2 commity, 1 zápis pod 50 kB, 1 overlay dotaz.
   - **Pan a zoom na plném oddálení:** FPS a počet DOM uzlů (`document.querySelectorAll('*').length`).
4. Skripty ze scratch převzít do repa jako regresní bench (návrh: `tools/perf/bench_board.perf.ts` přes
   vlastní vitest config a `tools/perf/bench_synthetic.py`) a hlídat sloupce z §3.

## 7. Co nerozbít

- Přenos `measured`, `width` a `height` při přestavbě uzlů (`Board.tsx:359-368`). Bez něj React Flow skryje
  nově postavené uzly do přeměření a textarea v kartě ztratí fokus. U opravy 3 platí totéž pro znovupoužitý
  i nově postavený uzel. U opravy 5 navíc pro uzly, které se teprve objeví ve viewportu.
- Handle portů bloků a karet musí zůstat ve všech úrovních detailu, jinak hrany zmizí nebo se odpojí.
- Ukládá jen rodič (App). Akce přes kontext (oprava 3) jen bublají nahoru, nic neukládají.
- Polling dál přes sdílený poller (P1): žádný `setInterval`, ve skryté záložce stojí.
