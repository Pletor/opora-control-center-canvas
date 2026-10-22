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

Upravené pořadí PR:

1. Jednorázový **návrh `sourceRef`** pro existující karty: deterministicky podle shody názvu karty a cesty v Graphify, jako `graph-changes` k lidskému přijetí.
2. D1 backend `plan_reality`.
3. D3 checklist.
4. D5 Lens → `sourceRef` po sloučení.
5. D2 návrhy z nálezů.
6. D4 vrstva v Lens.
7. D6 kancelář.

## Otevřené otázky pro člověka

1. **Karty mimo oblast** (v Opoře 49 ze 77): mají se počítat jako „bez oblasti“ (jako teď), nebo je chceš nejdřív rozmístit do oblastí?
2. **Kroky ve stavu karty vs. `spec.steps`:** mají se kroky z karty (`text`, `done`) převést do přijatého zadání (s `acceptance` a `dependsOn`), aby šla počítat slepá ulička a „další krok“ na úrovni kroků?
3. **Jednorázové navázání `sourceRef`:** stačí návrh podle shody názvů s ručním potvrzením, nebo chceš cesty zadávat sám?
4. **Projekt agent-office v Opoře** nemá `graphify-out` v hlavním checkoutu: zapnout pro něj obnovu map?
