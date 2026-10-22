# Záměr: Plán vs. realita (kolik plánu je hotovo a co se musí změnit)

Stav: **záměr**, žádný kód aplikace. Read-only měření je v `tools/plan-vs-realita/`.

## Proč

Karty na plátně jsou **plán, který se realizuje**. Člověk potřebuje jedním pohledem vidět:

- kolik procent zamýšleného plánu je hotovo (karta → oblast → projekt),
- co zbývá a co je **další proveditelný krok**,
- kde je slepá ulička, kde musí vzniknout nová cesta, úkol nebo port,
- co doplnit, co ubrat a co vyměnit, protože se realita rozešla se záměrem.

Vše deterministicky z dat, která Opora už má. Model (LLM) jen vysvětluje, nikdy nepočítá.
Každý nález je **návrh změny**, který přijímá člověk. Nic se nezapisuje přímo.

## Navazuje na

- PR Lens na uzlech (karta = Lens změny, oblast = mapa „jak to funguje“, projekt = horní pohled z oblastí s drill-down). Kancelář: `Pletor/agent-office#45`, Canvas `#38`.
- Kostra kódu z Graphify (`graphify-out/graph.json`, AST, bez modelu). Vazby mezi soubory se z něj dají odvodit (`imports`, `imports_from`, `calls`).
- Oblast je geometrický magnet (`backend/canvas/areas.py:20` `area_of`): karta patří do nejmenší oblasti, ve které leží její střed.
- Kód oblasti = `sourceRef` jejích karet (`existing` cesta, `planned` = teprve vznikne; `backend/canvas/graph.py:76-93`), později i soubory ze sloučených PR Lens.

## Zdroje dat (ověřeno v kódu)

| Co | Kde | Čtení |
|---|---|---|
| Přijatý plán karty (`goal`, `acceptance`, `steps[]`) | `opora_spec_revisions` + `opora_spec_refs.accepted_id` (`database/schema/project_schema.py:273,277`) | `GET /api/node-spec?node=` → `plan.accepted`; `opora_plan_steps.py:78,94,100` |
| Průběh kroků (`stepResults` done/failed/skipped) | `opora_execution_results.record` (`opora_execution_schema.py:11`) | `opora_step_results.reports()` `:88`, `progress_detail` `:147` |
| Bloky (open/met/unmet/blocked, onMet/onUnmet, porty, todos) | `desktop_v3_state.state` → `nodes[id].blocks` (`desktop_v3_state.py:59-80`) | `GET /api/desktop-v3/state` |
| Uzavření karty `done {confirmed, by}` | tamtéž (`desktop_v3_state.py:89`) | tamtéž; `confirmed` píše jen člověk |
| Plátno: oblasti, `sourceRef`, vazby a porty (`next/action/rule/block/flow`) | `graph.json` pracovního prostoru nebo `workspace_graph_authority` | `GET /api/view` |
| PR karty (open/merged/closed, head, merge) | `opora_execution_pull_requests` | `opora_card_done.link_for` `:38` |
| PR Lens karty | `opora_review_lens` (`opora_review_gate_schema.py:19-24`) | `opora_review_lens._rows(node_id)` `:91` (vrací všechny, nejen nejnovější) |
| Kostra kódu | `graphify-out/graph.json` v hlavním checkoutu (`map_artifacts.main_project_root` `:51`) | soubor |

Co už existuje a použije se znovu (nepsat podruhé): `progress`/`progress_detail` (`opora_step_results.py:141,147`), `card_plan`/`dod` (`opora_agent_state_steps.py:42,47`), `closure_gate` se šesti požadavky (`opora_card_done.py:63`), read-only `GET /api/sync-report` (`sync_report.py`, už pracuje s oblastmi), ve frontendu `stepsBadge` a `card-dod.ts`.

## A) Míra hotovosti

**Jednotka plánu:** krok (`steps[]`). Karta bez kroků: každý list bloku. Karta bez kroků i bloků: karta sama = 1 jednotka.

**Tři úrovně důkazu, vždy zvlášť, nikdy sečtené do jednoho čísla:**

| Úroveň | Jednotka je hotová, když | Co říká |
|---|---|---|
| **Agent tvrdí** | krok `done` ve `stepResults` / blok `met` / navržené uzavření | práce proběhla podle výstupu agenta |
| **Kód existuje** | `sourceRef` `existing` ukazuje na existující soubor/složku; později: sloučený PR karty (`state = merged`) a soubory z jeho Lens odpovídají `steps[].files` | v `main` je kód |
| **Potvrzeno člověkem** | `done.confirmed = true` | člověk kartu uzavřel |

Agregace: karta → oblast (podle `area_of`; mimo oblast = „bez oblasti“) → projekt, váženo počtem jednotek.
Rozdíl úrovní je sám signál: „agent tvrdí 80 %, kód 40 %“ = práce není v `main`.

## B) Diagnostika (deterministická pravidla)

| Typ | Pravidlo | Návrh změny (přijímá člověk) |
|---|---|---|
| **Zbývá** | otevřené jednotky; **další krok** = nehotová karta, jejíž všechny příchozí `next` jsou hotové, nebo krok, jehož `dependsOn` jsou hotové | — (pořadí práce) |
| **Slepá ulička** | blok `unmet`/`blocked` s `onUnmet.kind = none`; port bloku bez vazby; nehotová karta bez jediné vazby `next`; karta, jejíž předchůdce má blok `unmet`/`blocked`; opakovaně selhávající krok (`stepResults failed`, `lease.expired`) | nastavit `onUnmet`, nová vazba nebo zrušení kroku |
| **Nová cesta** | vazba v kódu (Graphify) mezi oblastmi, mezi kterými plán nemá `flow` ani vazbu jejich karet | `graph-proposals`: vazba `flow` mezi oblastmi |
| **Nový úkol / port** | kód bez karty (sirotek); PR Lens karty mění soubory mimo `steps[].files` | `graph-proposals`: nová karta nebo port; zařazení sirotka do oblasti podle většiny vazeb |
| **Doplnit** | karta bez `sourceRef`; karta bez kroků, bloků i kritérií; krok bez `acceptance`; prázdná oblast | `changesets`: doplnit pole zadání |
| **Ubrat** | dvě a více karet nad stejnou cestou; plánovaná položka, jejíž kód Lens označil `removed` | `graph-changes`: `removeNodes` / sloučení |
| **Vyměnit** | `sourceRef planned`, ale cesta už existuje (plán realizován, mapa neaktualizována); `existing`, ale cesta chybí (přesunuto/smazáno); skutečné soubory karty z Lens ≠ plánované | `graph-changes`: `updateNodes` `sourceRef` |

Mechanismy návrhů existují: `POST /api/oporahub/graph-proposals` (přidání i `graph-changes` s `updateNodes/removeNodes/updateEdges/removeEdges`), `POST /api/oporahub/changesets` (pole zadání), `POST /api/oporahub/content-changes`. Přijetí je vždy jen lidské.

**Pokrytí kódu plánem** = podíl souborů z Graphify pokrytých `sourceRef existing` (soubor nebo nejdelší předpona složky). Sirotci se nikdy neschovávají: pruh „Nezařazeno“, návrh oblasti podle většiny vazeb, sdílený kód jako oblast „Společné“.

## C) Zobrazení (jen popis)

- **Detail karty, záložka Kroky:** checklist kroků se třemi úrovněmi důkazu (ikonka agent / kód / člověk) a s odkazem na důkaz (běh, PR, Lens).
- **Záložka Lens u oblasti:** mapa oblasti s vrstvou plán vs. realita: plné části = kód existuje, „plán“ = plánováno, šedé = sirotek, červený okraj = slepá ulička.
- **Projekt:** horní pohled z oblastí, u každé tři procenta a počty nálezů; proklik do oblasti.
- **Kancelář:** okno Lens u Živého procesu ukáže totéž pro kartu, na které se zrovna pracuje.

## D) Rozpad na PR (každé samostatně z čerstvého `main`, s testy)

1. **Backend: `plan_reality` modul** (čistá funkce nad view + state + Graphify + PR/Lens) a `GET /api/oporahub/plan-reality?project&workspace[&area]`. Znovu použije `progress_detail`, `area_of`, `closure_gate`. Read-only.
2. **Návrhy z nálezů:** u nálezu tlačítko „připravit návrh“, které vytvoří `graph-proposal`/`changeset` k lidskému přijetí (nic se nezapisuje přímo).
3. **Frontend: checklist v záložce Kroky** (tři úrovně důkazu).
4. **Frontend: vrstva plán vs. realita v Lens oblasti a projektu.**
5. **Po sloučení PR:** soubory z Lens → návrh `sourceRef planned → existing`.
6. **Kancelář:** okno Lens u Živého procesu (samostatný modul v `agent-office`).

## Rozhodnutí člověka (22. 10. 2026)

1. **Oblast = jedna sekvence schopnosti** (přihlášení → platební brána → ověření platby → uložení do DB → vpuštění do kurzu; každá šipka jiná oblast). Každá oblast má princip, plán a definici „funguje“. Oblasti spolu tvoří jeden produkční celek. Sirotci jsou legitimní (individuální metoda, komponenta, API, i izolované).
2. **Volná ruka, zaznamenaná rozhodnutí.** Karta má svou pipeline. Výsledek stojí na důkladném zadání. Další karta navazuje se správným kontextem a nikdy nezačíná od nuly. Deterministické je vše, co jde (skripty, zobrazení, animace, signály); LLM je pro personalizaci a individuální plán a vidí proces i signály.
3. **Na plátně pracuje hlavně agent.** Vazby „co k čemu patří“ ano, ale nesmí zahltit paměť prohlížeče ani kontext agenta, ani u hlubokého vícevrstvého plátna.
4. **Zapnout Graphify pro agent-office.**

## E) Oblast jako sekvence

**Nová úložiště nejsou potřeba, oblast už pole má:**

| Co oblast potřebuje | Kde už je | Stav |
|---|---|---|
| Princip řešení | `purpose` oblasti, do 12 000 znaků (`backend/canvas/graph.py:206`; `docs/pyramida.md:17` „záměr“) | existuje |
| Plán | node-spec oblasti, `goal` (`/api/node-spec` nekontroluje druh, `canvas_service.py:217-248`; `docs/scenare-vrstvy.md:61` C4 hotovo) | existuje |
| Definice „funguje“ | node-spec oblasti, `acceptance` | existuje |
| Předávka do další oblasti | vazba `flow` (`graph.py:281-285`) nese jen `{id, source, target, port}`. Data předávky jdou do zprávy na vazbě `state.edges[id].handoff` (`desktop_v3_state.py:92-98`) | existuje, jen se nečte (níže) |
| Spustitelná kontrola „funguje“ | `scenario {command}` je dnes jen pro kartu uzlu (`graph.py:185-188`) | **nové:** povolit i na oblasti |

**Kdy je oblast hotová.** Dnes má oblast jedinou kontrolu: všichni její členové jsou zelení a prázdná oblast nikdy (`sync_verdicts.py:46-50, 99-103, 150-155`). Přibudou tři kontroly v `_checks_for`:
1. oblast má princip, plán i definici „funguje“,
2. její `scenario` prošel,
3. každá odchozí `flow` má neprázdný `handoff`.

**Kdy funguje celek.** Oblasti seřazené po vazbách `flow` dávají produkční tok projektu. Celek funguje, když je zelená každá oblast na řetězu a end-to-end `scenario` poslední oblasti prošel. Dnes to nic nepočítá, je to **nové**.

**Předávky v kontextu karty.** `areaFlows` v node-brief nese jen jména (`node_brief.py:252-266`), bez zprávy. Přidá se `report` (stejně jako `graph.incoming[].report`), takže karta uvidí, co jí předchozí oblast předává.

**Dva druhy sirotků:**
- **Záměrně samostatné:** nové volitelné `card.scope: "samostatne"` (`CARD_VALUES`, `graph.py:33-38`), u sektoru top-level `standalone: true`. Do pokrytí se nepočítá jako chyba, v přehledu má vlastní pruh „Samostatné“.
- **Nezařazené:** karta mimo oblast bez značky a kód bez karty. To je nález s návrhem zařazení podle většiny vazeb z Graphify.

Pravidlo **Sirotek** z kapitoly B se tím dělí na `SAMOSTATNE` (informace) a `NEZARAZENO` (nález).

## F) Pipeline karty, rozhodnutí a předávka

**Pipeline už existuje** (`docs/karta-pro-agenty.md:254-309`, `card_pipeline.py`):
- router vybere profil,
- etapy jdou work → test → review → fix → critic, každá v nové relaci (lease → node-brief → `agent-output` → release),
- selhání vloží `fix`, po dvou smyčkách je karta `stuck` a čeká na člověka.

**Rozhodnutí dnes:** `agent-output.decisions` je seznam holých textů (`agent_output.py:72-73`), uložený jako `{id, text, pinned, path, nodeId, createdAt, by}` (`desktop_v3_state.py:48`). **Chybí proč, alternativy, důkaz a kdo přesně.** Další karta je dostane přes `memory_for` (připnutá, předci, cesta; `desktop_v3_packets.py:136-141`) a od přímých předchůdců přes `upstreamDecisions` (`upstream_context.py:6-23`).

**Návrh (zpětně kompatibilní):** položka `decisions` smí být text **nebo** objekt:

```json
{"text": "Platbu ověřujeme webhookem, ne pollingem",
 "why": "brána garantuje doručení, polling by zdvojil dotazy",
 "alternatives": ["polling po 5 s", "ruční potvrzení"],
 "evidence": ["backend/pay/webhook.py:12-40", "PR #51", "test_webhook_retry"],
 "scope": "area", "agent": "opus/work"}
```

Klíče v `DECISION_KEYS` jsou volitelné a starý text funguje dál. Vzor pro tvar je rozhodnutí duelu Schránky (`brief_vault_duel_shape.py:94-106`).

**Pravidlo volné ruky:** v hranicích `must/must_not` a `acceptance` agent volí sám. **Musí zaznamenat** každé rozhodnutí, které:
- mění něco jiné kartě nebo oblasti,
- odchyluje se od plánu,
- vybírá mezi alternativami.

Rozhodnutí se `scope: "area"` dostanou všechny karty oblasti. `memory_for` dnes oblast nezná, protože oblast není předek, takže přibude shoda podle `area_of`.

**Signální balíček** `brief.context.signals`: deterministický, LLM ho jen čte. Zapojí se v `NodeBrief._assemble` vedle `card_lessons` (`node_brief.py:520-531`). Obsah seřazený podle důležitosti:
1. plán vs. realita mé karty a oblasti: otevřené jednotky, další krok, slepé uličky, které se mě týkají,
2. moje oblast: princip, plán, definice „funguje“, předávky dovnitř a ven se zprávou,
3. PR Lens předchůdců a mapa oblasti, jen názvy částí a soubory,
4. sousedé z Graphify u souborů mé karty, top N podle vah, přednostně vazby přes hranici oblasti (dnes brief nese jen cesty k Graphify, `node_brief.py:141`),
5. rozhodnutí oblasti.

**Rozpočet:** celý balíček nejvýš 8 kB a každá sekce má limit položek. Co se nevejde, je v `omitted` s počtem a odkazem na endpoint, odkud si to agent dotáhne. Dnes má node-brief jen limity po polích a žádný celkový (493 kB při 1600 kartách, `docs/navrhy/2026-10-14-vykon-platna.md`).

## G) Hluboké plátno bez zahlcení

**Co už je hotové** z `docs/navrhy/2026-10-14-vykon-platna.md`:
- hrany v `useMemo` (`board-edges.ts:39-49`), index vrstev (`board-index.ts`), stabilní `data` (`stable-nodes.ts:57`),
- LOD při oddálení (`card-lod.ts:7`, `FAR_ZOOM = 0.45`), `onlyRenderVisibleElements` od 80 uzlů (`layer-nodes.ts:36-39`, `Board.tsx:333`),
- polling bez prázdných překreslení (`same-response.ts`, debounce 400 ms), štíhlé zápisy (`/api/desktop-v3/node`, `/api/graph/positions`),
- MiniMap skrytá nad 500 uzlů, rovné hrany nad 1000.

**Co chybí:**
- Graf i celý stav plochy se načítají **celé**, se všemi bloky všech karet (`App.tsx:363`, `state-store.ts:86-92`). To je 390 kB až 1,4 MB a 1267 kB při 1000 kartách; zápis celého stavu nad 2 MB končí 413.
- Node-brief nemá celkový strop.
- Neexistují hierarchické souhrny.
- Syntetický generátor a frontendové perf testy z 14. 10. zůstaly mimo repo.

**Princip „vidím vrstvu, znám souhrn“:**
1. **Prohlížeč načte jen aktuální vrstvu** a o úroveň hlouběji jen **souhrny**: počet karet, tři procenta, počty nálezů. Plné karty hlubších vrstev nenačte. Nové `?layer=` na `/api/view` a `/api/desktop-v3/state` má precedens v `card-checklist?layer=` (`desktop_v3_routes.py:126-133`). Opuštěné vrstvy drží LRU cache N vrstev, ostatní se uvolní.
2. **Server počítá souhrny** projekt → oblast → karta inkrementálně podle revize a digestu, s ETag (už je u stavu, `desktop_v3_routes.py:203`). Plán vs. realita se počítá po oblastech a cachuje, ne při každém pollingu.
3. **Agent nikdy nedostane celý graf.** Čte hierarchicky: souhrn projektu (oblasti, procenta, toky, počty nálezů) → souhrn oblasti → brief karty. Zbytek dohledá přes `canvas-index` (`search`) a `rlm rank`.

**Měřitelné cíle** (návrh k potvrzení):

| Co | Cíl |
|---|---|
| Heap prohlížeče, projekt s 2000 kartami | ≤ 150 MB |
| Přepnutí vrstvy | ≤ 200 ms |
| Payload jedné vrstvy | ≤ 300 kB |
| Nečinnost / tah | dle §6 z 14. 10.: 0–2 commity za 60 s, ≥ 45 fps |
| Node-brief / signální balíček / souhrn projektu | ≤ 64 kB / ≤ 8 kB / ≤ 16 kB |

**Jak se to změří:** syntetický generátor se přesune do `tools/perf/`; heap přes Playwright a CDP; velikosti payloadů přes `bench_gets.py`.

## H) Graphify pro agent-office

- Automatika map je zapnutá. Poslední běh pro agent-office ale **selhal**, protože Opora bere nejvýš 500 zdrojových souborů (`backend/project/maps/graphify_worker.py:28`) a její checkout agent-office jich měl 680.
- Dnešní `main` agent-office má 858 souborů s kódem. `.graphifyignore` (Pletor/agent-office#47) vyřadí testy, nástroje, data map a 3D scenérii, zvuk a hry. Zůstane **520 souborů samotného produktu**, pořád přes limit. Měřeno `graphify.detect` 0.9.24, stejným voláním jako worker.
- Checkout agent-office v Opoře stojí na `8e95ca5` z 18. 10. a před obnovou mapy potřebuje synchronizovat `main`.
- Graphify je lokální AST bez modelu, takže navýšení limitu (třeba na 1500) nic nestojí na modelu, jen čas běhu. Bez toho nedostane LLM přehled o agent-office. Pokrytí agent-office proto zatím změřit nejde.

## Pořadí PR (nahrazuje předchozí)

1. **Graphify pro agent-office:** sloučit agent-office#47; v Opoře navýšit limit souborů; synchronizovat checkout; obnovit mapu.
2. **Jednorázový návrh `sourceRef`** pro existující karty (`graph-changes` k lidskému přijetí).
3. **Rozhodnutí jako objekt** (text nebo objekt, zpětně kompatibilní) a rozhodnutí oblasti v kontextu karet.
4. **Oblast jako sekvence:** kontroly oblasti (princip, plán, funguje, předávka), `scenario` na oblasti, `report` v `areaFlows`, `card.scope: "samostatne"`.
5. **Backend `plan_reality`** a signální balíček v node-brief s rozpočtem.
6. **Načítání po vrstvách a hierarchické souhrny** včetně perf nástrojů v `tools/perf/`.
7. Checklist kroků, vrstva v Lens, návrhy z nálezů, Lens → `sourceRef` po sloučení, okno v kanceláři.

## Měření na skutečných datech

Doplněno níže z `tools/plan-vs-realita/mereni.py` (jen GET na `127.0.0.1:8740` a čtení souborů).

Měřeno 22. 10. 2026 na třech projektech (`python tools/plan-vs-realita/mereni.py --project … --workspace … --out …`).

| | OPORA (vývoj aplikace) | agent-office | ample |
|---|---|---|---|
| Karty / jednotky plánu | 77 / 132 | 44 / 68 | 152 / 389 |
| **Agent tvrdí** | 27,3 % | 8,8 % | 44,7 % |
| **Kód existuje** | 0,0 % | 0,0 % | 0,3 % |
| **Potvrzeno člověkem** | 29,5 % | 0,0 % | 42,9 % |
| Pokrytí kódu plánem (Graphify) | 0 % (0/222 souborů) | n/a (bez `graphify-out`) | 0 % (0/441) |
| Karty mimo oblast | 49 ze 77 | — | — |
| Zbývá (otevřené jednotky) | 62 | 42 | 113 |
| Slepá ulička | 40 | 20 | 33 |
| Doplnit | 132 | 65 | 168 |
| Nová cesta / Ubrat / Vyměnit | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

Rozpad hlavních nálezů:

- **Doplnit `sourceRef`:** 77/77, 44/44 a 151/152 karet. V ample je 135 uzlů `planned` s prázdnou cestou, 48 bez `sourceRef` a **jediný** `existing` s cestou.
- **Slepá ulička:** většinou nedokončená karta bez jediné vazby `next` (31 / 20 / 15), dále porty bloků bez vazby (6 / 0 / 16) a bloky `unmet`/`blocked` bez `onUnmet` (3 / 0 / 2).
- **Doplnit zadání:** karta bez kroků, bloků i kritérií (41 / 20 / 17), krok bez `acceptance` (14 v Opoře).

Co je přesné a co odhad:

- **Přesné:** procenta „agent tvrdí“ a „potvrzeno“ (přímo ze stavu karet), počty slepých uliček a „doplnit“ (deterministická pravidla).
- **Zatím nevypovídající:** „kód existuje“, pokrytí, nová cesta, ubrat, vyměnit. Všechna stojí na `sourceRef` s cestou a ten v datech skoro není, proto nuly. Neznamená to, že kód chybí, ale že **plán není s kódem propojený**.
- **Tabulky OporaHubu** (`opora_spec_revisions`, `opora_executions`, `stepResults`, PR, Lens) jsou ve všech 13 projektech prázdné. Skutečné kroky dnes žijí ve stavu karty jako `{id, text, assignee, done}` bez `acceptance` a `dependsOn`. Výpočet proto čte stav karty a přijatý plán použije, až bude existovat.
- **Odchylky skriptu od pravidel:** `sourceRef` s prázdnou cestou se počítá jako žádný; „další krok“ vyžaduje aspoň jednu příchozí `next` (jinak by byly „další“ všechny kořeny); oblast bez jména se ukazuje jako prázdný řádek.

**Hlavní zjištění:** dnes jde spolehlivě měřit **„kolik je odškrtnuto“**, ne **„kolik je v kódu“**. Než bude mít smysl vrstva plán vs. realita v Lens, musí karty dostat cestu ke kódu. Proto je navázání `sourceRef` (D5 a jednorázové doplnění) první na řadě, ne poslední.

Pořadí PR je v kapitole „Pořadí PR (nahrazuje předchozí)“ výše.

## Otevřené otázky pro člověka

Otázky z 22. 10. rozhodl člověk (kapitola „Rozhodnutí člověka“). Nové:

1. **Limit Graphify v Opoře:** navýšit z 500 na 1500 souborů (bez modelu, jen čas běhu), aby agent-office dostal mapu?
2. **Synchronizace checkoutu agent-office v Opoře** (stojí na 18. 10.): smím ji spustit před obnovou mapy?
3. **Rozpočty a cíle v kapitole G:** sedí čísla (heap ≤ 150 MB, vrstva ≤ 300 kB, signály ≤ 8 kB), nebo je chceš jinak?
4. **`scenario` na oblasti** jako spustitelná definice „funguje“: souhlas?
