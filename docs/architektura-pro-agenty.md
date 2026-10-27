# Architektura pro agenty: mapa jako zadání, test a zpětná vazba

[Zpět na README](../README.md).

Stav: kontrakt schválený 2026-10-27, kód ho provádí po etapách (§9). Navazuje na
[pyramidu](pyramida.md), [kartu pro agenty](karta-pro-agenty.md), [architekturu projektu](architektura-projektu.md)
a [domény a worktree](domeny-a-worktree.md). Kde se s nimi liší, platí tento dokument a ty se upraví ve stejném PR,
které změnu provádí.

## 1. Proč

Mapa architektury domény je primárně **harness agentů**. Agent z ní ví, co stavět, kudy teče
zákazník i data a čím je hotovo; nemusí kvůli orientaci číst kód. Člověk z ní vidí celý obraz a píše jen
záměr. Každá **cesta zákazníka z bodu A do bodu B** je zároveň zadání i test: aplikace je pro člověka
nerozbitná, když všechny její cesty procházejí na skutečném kódu.

Smyčka: člověk napíše záměr → agent rozloží stránku (dávka `canvas-plan`) → kontrola mapy najde díry bez
modelu → člověk potvrdí dávku jedním rozhodnutím → agent staví s výřezem mapy v `node-brief` → harness ověří
cestu → výsledek se zapíše na mapu a do paměti role.

## 2. Kdo co píše (pyramida přes mapu)

| Úroveň | Prvek | Píše | Obsah |
|---|---|---|---|
| 0 Projekt | aplikace (`site.kind = "application"`) | člověk | prostředí, **cesty zákazníka** (`journeys`) |
| 1 Stránka | `site.kind = "page"` | člověk | `goal`, `feel`, `navLabel`; pořadí v menu dává pořadí uzlů (beze změny) |
| 2 Sekce | `site.sections` stránky | člověk ve formuláři stránky; agent smí navrhnout v dávce | role, název, záměr sekce |
| 3 Komponenta | uzel pod stránkou | agent | `card.section`, `card.tech`, `card.states`, `sourceRef`, kontroly |
| Vazby | hrany | agent | `carries` (druh toku) |
| Brána | cesta A → B | stroj | výsledek ověření cesty |

Člověk pod úrovní sekcí nic nevyplňuje (pyramida §4). Formuláře pro člověka jsou jen na aplikaci a stránce;
sekce jsou součástí formuláře stránky, protože člověk určuje, co na stránce má být (rozhodnutí 2026-10-27).

## 3. Datový model (jen přidává)

Všechna nová pole jsou **nepovinná** a **nikdy se nedoplňují výchozí hodnotou**. Chybějící pole znamená
„neurčeno“. Důvod: záznamy OporaHubu (návrhy a změny grafu) jsou adresované obsahem a při čtení se znovu
odvozují; přidaný výchozí klíč by starý záznam zneplatnil a změnil digest každého pohledu.

### 3.1 Stránka (`site.kind = "page"`)

```json
{ "kind": "page", "path": "/kontakt",
  "goal": "Poptávka odeslaná do 2 minut",
  "feel": "klidně, důvěryhodně",
  "navLabel": "Kontakt",
  "sections": [
    { "id": "hero", "role": "hero", "name": "Hero", "intent": "Ozveme se do 24 h" },
    { "id": "form", "role": "cta", "name": "Formulář", "intent": "Jméno, e-mail, popis" } ] }
```

- `goal` 1–200 znaků, `feel` 1–120, `navLabel` 1–40. Prázdný řetězec se neukládá, pole se vynechá.
- `sections` 1–20 položek; `id` jako id uzlu, jedinečné ve stránce; `role` ∈ `hero | cta | form | content |
  gallery | proof | faq | footer | custom`; `name` 1–60; `intent` 0–200.
- Proč v `site`, ne jako bloky: bloky žijí ve stavu pracovního prostoru (`state.nodes[id].blocks`), kdežto
  architektura je sdílená (`ARCHITECTURE_WID`). Sekce v `site` mají jednu pravdu, verzují se s revizí
  architektury, obnova revize je vrátí a smazání stránky nezanechá sirotky.

### 3.2 Aplikace (`site.kind = "application"`)

```json
{ "kind": "application", "environments": [{ "name": "Vývoj", "host": "localhost:3000" }],
  "journeys": [ { "id": "poptavka", "name": "Poptávka z menu", "from": "nav", "to": "<id stránky /dekujeme>" } ] }
```

- `journeys` 1–20 položek (bez cest pole vynechte); `id` jako id uzlu, jedinečné v aplikaci; `name` 1–80;
  `from` je id stránky aplikace nebo `"nav"` (vstup z menu); `to` je id stránky aplikace, jiné než `from`.
  Kroky cesty se **neukládají**, odvodí je stroj (§6). Zadává je člověk v mapě domény (panel „Cesty zákazníka“).
- Uložení neověřuje, že `from`/`to` stránka existuje: smazání stránky nesmí zablokovat mapu. Cestu s chybějícím
  koncem ohlásí kontrola mapy jako `journey.broken` a editor ukáže „chybí stránka“.
- `healthPath` zůstává beze změny (čte ho `web_status`).

### 3.3 Komponenta (uzel pod stránkou)

- `card.section`: id sekce (`site.sections[].id`) nejbližší stránky mezi předky karty (nejbližší předek se
  `site.kind = "page"` v řetězu `parentId`), kterou komponenta realizuje. Tvar id uzlu (`[A-Za-z0-9_-]{1,80}`),
  nepovinné, nikdy se nedoplňuje. Píše ho agent (dávka plánu: nová karta v `card`, existující v `extend` polem
  `section`, `null` smaže) a člověk v Detailu prvku (výběr „Sekce stránky“).
  - **Uložení grafu** (`validate_graph`) ověřuje jen tvar, ne existenci sekce: smazání sekce na stránce nesmí
    zablokovat uložení mapy (stejně jako cesty `site.journeys`, §3.2). Odkaz na chybějící sekci ohlásí kontrola
    mapy jako `section.unknown` a Detail prvku ho ukáže jako „chybí sekce …“.
  - **Dávka plánu** (agent) sekci, kterou zapisuje, ověří proti novému grafu a neexistující odmítne s důvodem;
    karta mimo stránku `card.section` mít nesmí.
- `card.tech`: 1–80 znaků, technologie realizace. `card.states`: 1–8 krátkých stavů
  (`prázdno`, `načítá`, `chyba`, `hotovo`…). Píše agent.

### 3.4 Hrana: `carries`

- Hodnoty `navigation | data | command | event`: navigace zákazníka, čtení dat, odeslání/zápis, událost.
- Název není `flow`: `flow` je už hodnota portu (tok mezi oblastmi, `backend/canvas/graph.py`).
- Smí ho mít hrana s portem `next` (i bez portu); hrana `flow`, `rule`, `action`, `block` ho mít nesmí.
- Port karty pro agenty (`next | action | rule | block`) se nemění. `carries` jen říká, co po vazbě teče.

### 3.5 Členství v oblasti

Zůstává **geometrické** (`areas.area_of`, `areaOf` na frontendu); `memberOf` beze změny. Změna sémantiky by
zneplatnila uložené záznamy změn grafu (odvozené `areaId`) a `contextVersion` rozpracovaných běhů.
Oblast při tahu karty roste (§8), ale nikdy nepřekryje cizí kartu ani oblast; kde by musela, karta se vysune ven
stejně jako dnes (`settleCard`).

## 4. Co dostane agent: `node-brief.architecture`

Nový klíč nejvyšší úrovně v `opora.node-brief/1`, **mimo `specification`**, takže nemění `contextVersion`.
Počítá ho backend deterministicky ze stejného grafu; nese jen větev karty. Strop asi 600 tokenů (2,5 KiB JSON).

```json
"architecture": {
  "journeys": [ { "id": "poptavka", "line": "nav → /kontakt[form] → POST /api/poptavka → db.poptavky → /dekujeme",
                  "youAre": 2, "lastRun": { "status": "failed", "failedAt": 3, "summary": "422 na POST" } } ],
  "page": { "path": "/kontakt", "goal": "…", "feel": "…", "section": { "id": "form", "role": "cta", "intent": "…" } },
  "in":  [ { "carries": "navigation", "from": "Navbar" } ],
  "out": [ { "carries": "command", "to": "POST /api/poptavka", "sourceRef": "api/poptavka.py" } ],
  "states": ["prázdno", "odesílá", "chyba", "hotovo"],
  "gaps": ["state.no-error"]
}
```

Karta mimo stránku (není pod žádnou stránkou) klíč nedostane. `lastRun` se objeví až s etapou 8.
Provádí `backend/project/architecture/node_architecture.py` (volá ho `node_brief.py`). Pravidla:

- **Bez výchozích hodnot.** Chybějící údaj = chybějící klíč; prázdný seznam (`journeys`, `in`, `out`, `gaps`)
  se vynechá, `states` jen když karta `card.states` má.
- `journeys`: jen odvozené (nerozbité) cesty (§6), v jejichž krocích karta je (krok s jejím `nodeId`, nebo
  stránka slitá do kroku své komponenty, `pageId`); `youAre` je index toho kroku (menu `nav` je krok 0).
- `page`: `path`, `goal` a `feel` jen když jsou; `section` = `{id, role, intent}` jen když karta má
  `card.section` a nejbližší stránka sekci s tím id má.
- `in` / `out`: hrany karty s `carries`, v pořadí id hrany; `from` / `to` je název uzlu na druhé straně (bez
  názvu id), `sourceRef` jeho `sourceRef.path`, jen když je.
- `gaps`: pravidla kontroly mapy (§5), jejichž nález míří na kartu (`nodeId`) nebo na její hranu (`edgeId`);
  každé jednou, v pořadí pravidel.
- **Strop** 2560 B kompaktního JSON v UTF-8. Ořez je deterministický: nejdřív cesty od konce (první zůstane),
  pak hrany od konce, delší z `in`/`out` dřív (při shodě `out`), nakonec i první cesta; ořezaný výřez nese
  `"truncated": true`.
- **Verze zadání.** Cesty zákazníka nejsou zadání karty: `site.journeys` aplikace se do `specification` (graf
  `_node` i porovnání starých záznamů `scoped_specification`) nepromítá, takže přidání, změna ani smazání cesty
  `contextVersion` nemění. Ke kartě se cesta dostane jen tady, odvozená.

## 5. Kontrola mapy

Čistá funkce bez modelu (nový modul `map_check` ve složce `backend/project/architecture/` s testem vedle). Spouští se nad
přijatou architekturou (čtení) a nad dávkou plánu i návrhem změny grafu (odmítnutí s důvodem). Výstup je seznam
`{rule, nodeId|edgeId|journeyId, message}`.

| Pravidlo | Kdy | Dopad |
|---|---|---|
| `journey.broken` | cesta nemá souvislou řadu kroků | dávka/návrh se vrátí agentovi |
| `section.unrealized` | sekce bez komponenty se `card.section` | práce pro rozkladače |
| `section.unknown` | karta odkazuje `card.section` na sekci, kterou nejbližší stránka nemá, nebo leží mimo stránku (`nodeId` karty) | práce (agent nebo člověk sekci opraví či zruší) |
| `command.no-receiver` | komponenta odesílá (`command`) a vazba nikam nevede | práce |
| `state.no-error` | komponenta s výstupem `command` nemá stav „chyba“ | práce |
| `edge.carries-unset` | hrana `next` mezi komponentami stránky bez `carries` | práce (migrace bez odhadu) |
| `page.no-goal` | stránka bez `goal` | jediná díra pro člověka |

Provádí `backend/project/architecture/map_check.py`; čtení nad přijatou architekturou je
`GET /api/project-architecture/map-check?project=`. `journey.broken` nese `journeyId` (id cesty v aplikaci) a zprávu
„Cesta <název>: <důvod>“; důvody jsou z odvození cesty (§6). Nálezy cest jdou první (aplikace podle id, cesty
v pořadí, v jakém je zadal člověk).

Díry jsou práce pro agenty **jen v potvrzené dávce**; k člověku jde souhrn jako jedno rozhodnutí
(pyramida, pravidlo 4).

## 6. Cesta zákazníka

Kroky odvodí stroj: z `from` (menu nebo stránka) po hranách `carries ∈ {navigation, command, data}` a přes
komponenty se `card.section` až k `to`. Nejkratší cesta, deterministické pořadí podle id. Bez souvislé cesty je
`journey.broken`.

Provádí `backend/project/architecture/journeys.py` (`derive_journeys`, čistá funkce bez modelu a I/O); čtení nad
přijatou architekturou je `GET /api/project-architecture/journeys?project=` →
`{journeys: [{applicationId, id, name, from, to, steps, line} | {applicationId, id, name, from, to, broken}]}`.
Přesná pravidla:

- **Stránky aplikace** jsou stránky, jejichž nejbližší aplikace v řetězu `parentId` je tato aplikace. **Menu**
  (`from: "nav"`) jsou ty z nich, mezi kterými a aplikací neleží jiná stránka (jako `parentPageId == null`
  v `specification.navigation`). Menu je jen začátek: z menu se vstoupí na kteroukoli stránku v menu, zpět do
  menu se cesta nevrací. Cíl, který sám je v menu, je z menu jedním krokem; stránka, na kterou se má dojít jen
  přes formulář (poděkování), patří pod jinou stránku jako podstránka.
- **Komponenta** je uzel pod stránkou (nejbližší stránka mezi předky, §3.3), který není stránka, aplikace,
  oblast ani komentář. **Komponenta se sekcí** má `card.section`, které nejbližší stránka má.
- **Kroky pohybu:** (1) hrana s `carries ∈ {navigation, command, data}` po směru `source → target` (`event` cestu
  nenese, oblasti a komentáře se neprocházejí); (2) stránka → její komponenta se sekcí (zákazník použije sekci);
  (3) komponenta → její stránka (výsledek, který dorazí do komponenty, vidí zákazník na její stránce).
- **Komponenta bez sekce:** ze stránky se do ní nevstupuje (nic neříká, kterou část stránky zákazník používá),
  po hraně (1) ji cesta projít smí. Důvod: API, databáze nebo služba pod stránkou sekci mít nemůže, a přesto
  leží na cestě; sekce je povinná jen pro vstup zákazníka ze stránky.
- **Nejkratší cesta** podle počtu kroků (BFS); startovní uzly i sousedé vzestupně podle id, každý uzel si
  pamatuje prvního předchůdce, takže remízu vyhraje cesta s menšími id dříve.
- **Kroky a `line`:** stránka = `site.path`, komponenta se sekcí = `/path[sectionId]` (cesta její stránky),
  ostatní uzly = název (bez názvu id), menu = `nav` (krok bez `nodeId`). Stránka hned před vlastní komponentou se
  sekcí se slije do jejího kroku (`pageId`), stejně stránka hned po ní, pokud to není cíl. Krok je
  `{nodeId?, label, pageId?}`, `line` = popisky spojené „ → “.
- **Rozbitá cesta** (`broken` místo `steps` a `line`): „chybí stránka X, kde cesta začíná.“, „chybí stránka X,
  kam cesta vede.“ (smazaná nebo z jiné aplikace), „z <začátek> na <cíl> nevede souvislá řada kroků …“. Brána: karta, jejíž komponenta leží na cestě, se neuzavře, dokud poslední ověření cesty
neprošlo (etapa 8). Test cesty dodává výbava harnessu projektu (`harness.kit/1`, kategorie `testing`; u webu
typicky Playwright). Opora nástroj nepředepisuje, vyžaduje doklad. Tvar dokladu upřesní dodatek tohoto kontraktu
v etapě 8.

## 7. Co člověk vidí

Na doméně dva pohledy na stejná data: **Stránky** (karta stránky se sekcemi, cesty) a **Studio** (tok podle
`carries` a stav cest podle posledního ověření). Velín: jedna fronta „Čeká na tebe“. Monitor procesů se nestaví.

## 8. Strom dopadů (co se musí upravit spolu)

Každá etapa upraví celý svůj strom v jednom PR, včetně testů, README dílků, skillu a dokumentů.

**Úklid karty (frontend):** `CardView` pole `doneProposed`, `openIdeas`, `briefChanged`, `cardModel`,
`cardEffort`, `cardStatus`, `design`, `round` (`frontend/editor/canvas/node-card/logic/card-model.ts`, `layer-nodes.ts`,
`card-model.test.ts`); `NodeCardData.usage` s řetězem `useUsage` → `Board` → `layer-nodes` (endpoint
`/usage-summary` zůstává, čte ho `node_brief.py`); duplicitní porty v `BriefTab.tsx`. Tóny `security`/`cache`
a `healthPath` **nejsou** mrtvé a zůstávají.

**Rostoucí oblast:** nová čistá funkce v `frontend/editor/canvas/area/logic/` (+ test) volaná z
`frontend/editor/canvas/board/components/Board.tsx` (tah) a `frontend/project/architecture-editor/page-editor/components/ArchitectureCanvas.tsx`
(`onNodeDragStop` dnes ukládá surovou pozici); zarážka o cizí kartu/oblast podle `solid-bodies.ts`; README
`area/` a `page-editor/`. `CENTRE_OFFSET` se nemění (musí sedět s backendem `areas._CENTRE_OFFSET`).

**Stránka a aplikace (`site`):** `backend/canvas/site_metadata.py` (+ `test_site_metadata.py`);
`specification_context.py` `_navigation` (navigace v node-briefu, přidat `navLabel`); `frontend/shared/types/logic/types.ts` `NodeSite`;
`ArchitectureProductForm.tsx` (oprava: změna cesty dnes zahodí ostatní klíče `site`); `ArchitectureDomainMap.tsx`;
`PageCard.tsx`, `DomainPanel.tsx`; `product-tree.ts` `productFingerprint`; `frontend/project/architecture-editor/element-detail/logic/agent-context.ts`;
docs `architektura-projektu.md`, `domeny-a-worktree.md`; skill `.claude/skills/opora-control-center/references/api.md`.

**Hrana `carries` a komponenta `section`:** backend `graph.py` (`EDGE_KEY_SETS`, kontrola hodnot; klíč karty
`card.section`), `canvas_plan_links.py`, OporaHub `opora_graph_build.py`, `opora_graph_records.py`,
`opora_graph_change_records.py`, `opora_graph_change_plan.py`, `opora_graph_change_diff.py`, `node_brief.py`
`link()`, `canvas_index.py`, `trace.py`, `plan_lens_views.py`; frontend `types.ts` `GraphEdge`,
`board-model.ts`, `editor-model.ts`, `canvas-model.ts` `edgeLook`, `agent-context.ts`,
`frontend/hub/oporahub-overview/logic/overview.ts` (otisk grafu), `frontend/hub/graph-proposals/logic/graph-edits.ts`
(dnes natvrdo `port: "next"`), `GraphProposalDetails.tsx`, `GraphChangeReview.tsx`; testy podle hlášení
dopadů (grafové porty, plán, návrhy a změny grafu, node-brief, specifikace); docs `karta-pro-agenty.md`,
`oporahub-graph-proposals.md`; skill `.claude/skills/opora-control-center/references/canvas-plan.md`, `workflow.md`, `planner.md`, `rozklad.md`,
`.claude/skills/opora-control-center/assets/task-brief.md` (příklady ověřuje `.claude/skills/opora-control-center/scripts/test_skill_docs.py`). Změna `carries` na existující hraně
mění digest pohledu a zneplatní rozpracovaný výstup obou koncových karet; to je správně.

**`node-brief.architecture` (hotovo v etapě 7):** `node_brief.py` (+ `test_node_brief.py`), výřez
`backend/project/architecture/node_architecture.py` a cesty `journeys.py` (+ testy), `journey.broken` v `map_check.py`,
čtení `GET /api/project-architecture/journeys`, projekce zadání bez `site.journeys` (`assignment_scope.py`,
`specification_context.py`), skill `.claude/skills/opora-control-center/scripts/opora_read.py`
(souhrn) + `test_opora_read.py`, `references/api.md`, `karta-pro-agenty.md`; v mapě domény odvozená řada u cesty
(`CustomerJourneys.tsx`).

## 9. Etapy

| # | Etapa | Kontrakt mění |
|---|---|---|
| 1 | Úklid karty | ne |
| 2 | Oblast roste s kartou | ne |
| 3a | Stránka: `goal`, `feel`, `navLabel`, `sections` | `site` |
| 3b | Aplikace: `journeys` | `site` |
| 4 | Hrana `carries`, komponenta `section`: 4a `carries` (samostatně), 4b `section` (až po 3a) | graf, návrhy grafu |
| 5 | Komponenta `card.tech`, `card.states` | `card` |
| 6 | Kontrola mapy (§5) + API | ne |
| 7 | Cesty (§6) a `node-brief.architecture` (§4), hotovo | node-brief |
| 8 | Brána cesty: harness, doklad, `lastRun` | dodatek |
| 9 | Pohled Studio | ne |

Každá etapa je samostatný PR z čerstvého `origin/main` (`docs/cista-linie.md`). Před odevzdáním:
`uv run pytest backend`, `npm test`, `npm run build`, u skillu i jeho testy.

## 10. Co se nestaví

Monitor procesů, porty OS, spouštění skriptů, simulace zátěže, vlastní úložiště stránek a úkolů vedle grafu,
formuláře pro člověka pod úrovní sekcí, změna geometrického členství v oblasti.
