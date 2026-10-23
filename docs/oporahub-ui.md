# Rozhraní OporaHubu (fáze 2): smyčka, karta, pro agenty

OporaHub (Alt+3) je jedna stránka nad jedním dokumentem
[`GET /api/oporahub/agent-state`](oporahub-agent-state.md). Vychází z návrhu Claude Design
„OporaHub — přehled“ (`01-prehled`, `02-karta`, `03-agenti`, tokeny `oh-tokens.css` převzaté
z `frontend/design-tokens`). Ukázková čísla návrhu se nepřebírají; vše je ze serverového snímku.

## Pohledy

| Pohled | Kde | Co ukazuje |
|---|---|---|
| **Přehled** (výchozí) | záložka Přehled | Horní pás: přijatá hlava, drift pracovní verze (a počet návrhů na starém základu), mix rizika čekajících návrhů, nejvýše 3 rozhodnutí člověka. Pod ním smyčka deseti etap `plan → … → plan_writeback` jako „had“ (1–5 zleva doprava, 6–10 zpět) se spojkami a pata se známými mezerami. |
| **Živý proces** | záložka Živý proces, nebo `?ohView=process` | Zdroje, blokace, mapa toku sedmi fází, proud událostí a inspektor karty nad sdíleným tokem událostí ([živý proces §8](zivy-proces.md#8-pohled-záložka-živý-proces-v-oporahubu)). |
| **Karta** | záložka Karta, klik na cíl `claim`, nebo `?ohCard=<nodeId>&ohTab=<záložka>` | Otevře [jednotný detail karty](#jednotný-detail-karty) (stejný drawer jako na plátně a ve Velínu). |
| **Pro agenty** | záložka Pro agenty, nebo `?ohView=agents` | Protokol (GET → preconditions → zápis s requestId → 409 znovu GET), hlavy pro CAS, fronta akcí (id, sloveso, metoda, cesta, preconditions, rozpočet, stav), přesný JSON s tlačítkem „kopírovat JSON“ a tabulka kontraktu `data-oh-*`. |

Rozhodnutí `close_card` (PR sloučeno, karta čeká na potvrzení člověkem) otevře detail karty, kde definice
hotovo ukazuje „Uzavřel člověk“ jako rozpracovaný dílek a patička akci `close_card`; kartu uzavírá jen člověk (`human_only`).
Klik na etapu, rozhodnutí nebo cíl akce otevře **existující** detail (návrh zadání/grafu/obsahu,
běh, důkazy, pravidla…). Pata „Podrobné formuláře“ dál otevírá všechny původní drawery: zadání karty,
návrhy grafu, změny obsahu, přijímání návrhů, pravidla přijetí, běhy, limity, proces Control Center,
důkazy a sledování GitHubu, pravidla review, formální podklady, rozhraní pro agenty a starší historii.
Každý drawer má ✕ vpravo nahoře; ✕ i Escape ho zavřou a vrátí focus.

## Jednotný detail karty

Jeden drawer pro celou aplikaci (`frontend/hub/oporahub-card-drawer`, návrh „Opora Editor — lean“, rámy 3a–3j
a datová mapa 6a). Nahradil inspektor `editor/node-detail` (záložky Zadání · Vazby · Práce · Podněty · Historie
kol) i starý drawer `hub/oporahub-card`. Otvírá ho kdokoli voláním `openCardDrawer(nodeId, tab?)` z
`frontend/hub/oporahub-card-drawer/open.ts`: dvojklik na kartu na plátně, odznak etapy, Velín, OporaHub
(záložka Karta, rozhodnutí, cíl akce) i tlačítko „Detail karty“ v inspektoru. Přímý odkaz
`?ohCard=<nodeId>&ohTab=spec|steps|lens|run|review|history` funguje v každém prostředí. ✕ vpravo nahoře i Escape
detail zavřou, vymažou parametry z URL a vrátí fokus na prvek, odkud byl otevřen.

| Část | Co ukazuje | Zdroj |
|---|---|---|
| Hlavička | Druh (`cards[].kind`), sektor a pořadí (`topoIndex`), název, **jeden stavový řádek** (značka + zdraví · etapa · důvod · odpočet lease) a držitel lease | `cards[]`, `…/executions` |
| Definice hotovo | Šest dílků v pořadí kontraktu §3: Kroky · Akceptace karty · Brána · Sloučeno · Plán zapsán · Uzavřel člověk. Zdrojem je `cards[].dod` z agent-state (šest booleanů, `gate` `review`/`external` → u brány „GitHub“, `done`, `missing`); jen starší server bez `dod` se dopočítá na klientovi z `cards[].steps`, brány, stavu PR, důvodu karty a událostí `merge.done` / `writeback.done` / `card.closed`. Akceptace karty a lidské uzavření bere z `GET /api/oporahub/process` (`acceptanceEvidence`, `doneConfirmed`); bez nich `◌ nenapojeno`. | `cards[]`, `…/process`, brána, události |
| Patička | Jediná další akce: `cards[].nextActionId` → `actions[]` (popisek, kdo ji dělá člověk/agent, `blockReason` česky); bez `nextActionId` první akce mířící na kartu nebo její běh | `actions[]` |
| **Zadání** | Přijaté × pracovní × rozdíl: cíl (s účelem komponenty), ne-cíle, akceptace karty po řádcích, kroky po ID (`+` přidaný, `−` odebraný, `~` změněný s výčtem polí). Čekající návrhy karty s rizikem a starým základem, konflikty auto-rebase, „Navrhnout změnu“ (pracovní zadání → `POST /api/oporahub/changesets`, přijímá člověk) a „Zahodit“. Ponechané editory ve sbalených oddílech: pracovní zadání + účel, Schránka, popis, nastavení karty, vazby. | `…/changesets/context`, `…/changesets`, `…/proposal-reviews` |
| **Kroky** | Postup `hotovo/celkem`, náhled DAG (sloupec = hloubka `dependsOn`), seznam kroků s druhem, akceptací (✓ u hotového kroku), závislostmi a tím, na co krok čeká; aktuální krok (`cards[].steps.current`, jinak první nehotový v topologickém pořadí) je rozbalený. Bez `spec.steps` poctivě „nenapojeno“. Změna kroků jde přes Zadání (changeset). Stav kroku bere z `cards[].steps.items` (souhrn všech běhů; krok hotový v dřívějším běhu zůstává hotový), důkazy z `stepResults` nejnovějšího běhu. | `fields.steps`, `cards[].steps.items`, `stepResults` |
| **Lens** | Prostor PR Lens mezi plánem a kódem (`frontend/hub/review-lens`): vizitka (PR, hlava, `validatedAt`, „spec 7 KB · 10 částí · 9 vazeb“, „Kopírovat spec pro agenta“), přepínač čoček architektura / tok dat podle `views` specu, přiblížení a posun, průvodce (`W`/→, ←, Esc) se zlatým okrajem na rámečcích atlasu, panel části (změna, popis, soubory s řádky a odkazy do GitHubu, vazby) a payload kroku toku (tvar, ukázka s rozdílem před/po). Odznak = krátká hlava PR, nebo „plán“ u mapy oblasti před kódem. Drawer se na této záložce rozšíří. Zrcadlo nese `lens: {kind, headSha, nodes, edges}`. Obrázek je `<img>` z Blob URL, nikdy `innerHTML`; renderer se načítá líně. | `…/review-lens?nodeId` |
| **Běh** | Odpočet lease (čas serveru, ne prohlížeče), exekuce, agent a epocha, snímek zadání (`acceptedRevision` · `assignmentDigest`), rozpočet pokusů/oprav/času, výsledky kroků s důkazy, samokontroly agenta; sbalená paměť agenta a worktree | `…/executions?nodeId`, `…/results`, `…/execution-budgets`, brána |
| **Review & PR** | Číslo PR, hlava, šablona, riziko, kolo, čerstvost vůči cílové větvi; brána se **všemi** důvody (blokuje / čeká) a splněnými pravidly; nálezy PR (otevřené a závažné nahoře); ověření lidé proti požadovanému počtu; formální důkazy (Lean, TLC, shoda + důvěra) | `…/review-jobs/gates`, `…/review-jobs`, `…/verifications?nodeId` |
| **Historie** | Události karty od nejnovější s filtrem Vše / Zadání / Běh / Review / Lidé, kurzor hlavy a export JSON; pod nimi přijaté revize a blame | `…/events`, `…/history/card`, `…/blame/card` |

`GET /api/oporahub/events` nemá filtr karty: detail stránkuje kurzorem (500 na stránku, nejvýš 10 stránek) a kartu
vybírá na klientovi; kořen záložky to říká atributem `data-oh-events-filter="client"` a zkrácení `data-oh-events-truncated`.
Data detailu se čtou jednou při otevření a po „Obnovit“ v patičce; jen agent-state jde ze sdíleného pollera.

Z detailu karty zmizely: záložky Podněty a Historie kol, předávka „Předat agentovi“ (`CardHandoff`), štítek
verdiktu Oracle, uzavření karty `DoneControl`, „Zacommitovat zadání“ (`/api/opora-commit`) a historie výsledků
starého `agent-output` (nahrazuje ji Běh s výsledky exekucí). Inspektor uzlu v Editoru je jen štíhlý rozcestník
(vnitřní plátno, balíček karty, Schránka, rozklad sektoru, smazání).

## Lens plánu

Plán jako diagram PR Lens, stejné plátno jako záložka Lens detailu karty (`frontend/hub/plan-lens`, kreslí
`hub/review-lens/LensStage`). Data: `GET /api/oporahub/plan-lens?project&workspace[&area=<id oblasti>]` →
`{kind: "plan", area, digest, spec, stats, graphify}`; obnova posílá `If-None-Match`, 304 drží zobrazená data.

| Kde | Co ukazuje |
|---|---|
| OporaHub · hlavička přehledu · **◫ Lens plánu** (detail `plan-lens`) | Celý projekt: oblasti a předávky mezi nimi. |
| Editor · inspektor oblasti · **◫ Lens oblasti** | Jedna oblast: její karty, vazby z plánu a šedé vazby „kód“ z Graphify; okno vyjede zprava, ✕ vpravo nahoře, Escape a klik vedle ho zavřou a vrátí fokus. |

Nad plátnem pruh čísel (oblasti, karty, s kódem, v plánu, samostatné, nezařazené; nula je bledá), stav
Graphify (`✓ · revize abc1234`, nebo „nedostupný · vazby „kód“ chybí“), legenda (plná část = kód existuje,
odznak „plán“ = plánováno, šedá vazba „kód“ = vazba z Graphify) a „Obnovit“. Panel části ukazuje i odznaky
uzlu. Starší server bez endpointu (404) dostane klidný stav „Lens plánu není na serveru k dispozici“ s
„Zkusit znovu“, ne chybu. Kořen nese `data-oh-view="plan-lens"`, `data-oh-plan-status`
(`idle`/`loading`/`ok`/`unavailable`/`error`) a `data-oh-plan-scope` (`project`/`area`); pruh
`data-oh-plan-digest`, `data-oh-plan-area`, `data-oh-plan-stat` a `data-oh-plan-graphify`.

## Vlna 5: brána review, lidé, metriky, auto-rebase, důkazy a plátno

| Kde | Co ukazuje | Zdroj |
|---|---|---|
| Přehled · etapa **Review** | Stav brány merge (`✕ blokuje` / `◷ čeká` / `✓ žádná brána nedrží` / `◌ automatické review vypnuto`) a kód pravidla, které ji drží; lidské znění je důvod etapy | `stages[review]` + `gaps` |
| Přehled · etapa **Návrh změny** | Počet otevřených konfliktů auto-rebase; klik otevře drawer konfliktů | `actions[verb=proposal.resolve_conflict]` |
| Pro agenty · fronta | Skupina slovesa (`brána review`, `ověření`, `auto-rebase`, `smyčka`) a `◷ pozornost`; česká jména pro `review.claim`, `review.self_checks`, `pr.update_branch`, `review.promote_to_check`, `verification.*`, `proposal.resolve_conflict` | `actions[]` |
| Detail karty · **Review & PR** (dřív krok Review · brána merge) | Na ose etapa karty (`cards[]`); pod osou panel brány: stav, pravidlo, které drží, všechny důvody, otevřené důležité nálezy, bezpečnostní review, požadovaná schválení proti **různým ověřeným lidem na hlavě** (`reviewGate.humans`), neověřená schválení, vlastní kontroly, `stale_against_main` (o kolik commitů), `template_incomplete` (chybějící sekce) a související akce | `GET /api/oporahub/review-jobs/gates` |
| Karta · **Formální důkazy** | Lean, TLC a shoda s implementací (`formal/conformance`, vždy `nahlášeno agentem`; bez záznamu `◌ bez záznamu`), výsledek, důvěra `nahlášeno agentem` / `ověřeno CI`, historický podklad; rozhodnutí `verification.fix` jako tlačítko „Založit návrh opravy“ (přijímá člověk) | `GET …/verifications?nodeId=` + `actions[]` |
| Karta · **Historie a blame** | Přijaté revize karty (i „auto-rebase z … · původně …“) a pro každý klíč poslední revize a autor | `GET …/history/card/{id}`, `…/blame/card/{id}` |
| Pata · **Konflikty auto-rebase** | Seznam konfliktů, tabulka `base / ours / theirs` po polích, volba strany, kopírovatelný návrh řešení, připojení nového návrhu (`…/resolve`) a „Spustit auto-rebase teď“ | `GET/POST …/auto-rebase/*` |
| Pata · **Metriky review** | Malá infografika: nálezy podle závažnosti, co se s nálezy stalo, přijetí a šum, odfiltrováno hlasováním, kola na PR, čas do rozhodnutí člověka, pojistky revertů a incidentů, počet eval případů a odkaz na `export.jsonl` | `GET …/review-metrics`, `…/review-evals` |
| Pata · **Kniha důkazů** | Počty podle stavu, filtr nástroje (Lean, TLC, Shoda), řádky s důvěrou, commitem a axiomy (axiom mimo povolené je zvýrazněn); v úzkém panelu (< 700 px) je každé tvrzení karta s řádky „stav / důvěra / commit / naposledy / axiomy“ bez vodorovného posouvání | `GET …/verifications/ledger` |
| Pata · **Lidé v review (jen člověk)** | Nárok identity → řádek `Opora-Identity: <id> <nonce>` ke zkopírování a vložení jako samostatný řádek komentáře na GitHub, ověření číslem PR/issue, registr (ověřeno / čeká / zrušeno, operátor), zrušení s potvrzením | `…/review-identities*` |
| **Plátno Editoru** | Stavový řádek tváře karty (viz [Editor lean](#editor-lean-tvář-karty-velín-a-živý-pás)); samostatný odznak nad kartou zrušen | `cards[]` agent-state |

**Nonce nikdy nejde agentovi.** Řádek `Opora-Identity` vrací server jen lidské session a UI ho ukazuje
jen jako text v draweru: není v žádném `data-oh-*` atributu ani v zrcadle `oh-review-identities`
(funkce `publicIdentities` ho odstraní, hlídá test).

## Editor lean: tvář karty, Velín a živý pás

Návrh Claude Design „Opora Editor — lean“ (rámy 1a/1b, 2a/2b, 4a/4b, 5a/5b). Jediný zdroj stavu je
agent-state; tok událostí je delta. Starší pipeline router/kritici, kontrolní pás, sloty dokladů a
návrhy uzavření z plátna zmizely (backend zůstává do pozdějšího PR).

| Kde | Co ukazuje | Zdroj |
|---|---|---|
| **Lišta Editoru** | Struktura · Velín · Text; `⋯` = Kreslení, Kancelář, Storyboard (aktivní mód z nabídky nese ⋯ jeho jméno); zpět/vpřed; jedno `+ Přidat` (Sektor, Uzel, Komentář, Oblast); jedno `Srovnat` (sloupce podle vazeb, ve sloupci podle `topoIndex`, pak původní místo) | `layout/mode-rail`, `editor/canvas/add-menu`, `ui-kit/toolbar-menu` |
| **Tvář karty** | Druh (`kind`, jinak vrstva) a kdo drží (A agent z `lease.holder`, H člověk u rozhodnutí); název; **jeden** stavový řádek `značka slovo · etapa · důvod` (u běžící karty odpočet lease); segmenty kroků `done/total · current Název`; nejvýš jedna patička: rozhodnutí > na koho čeká (`blockedBy`) > brána (`gate.rule`). Okraj: tyrkysový = agent běží, zlatý = čeká na tebe, čárkovaný = blokováno předchůdcem. Přednost stavu: hotovo > rozhodnutí > lease > blokováno > brána > zdraví. Pod 45 % zoomu glyf (značka, název, lišta postupu); nevybraná karta má z bloků jen číslo, název a úchyty, porty se ukážou najetím | `cards[]` (`stage`, `health`, `reason`, `kind`, `layer`, `blockedBy`, `gate`, `steps`, `lease`), `decisions[]` |
| **Hlava vrstvy** | `SEKTOR jméno` + počty karet podle tónu (✓ ▸ ◷ ● ✕ ○), `N karet · M vazeb next`, autonomie a závěrečná karta sektoru (dříve „Brána“, přejmenováno, aby se nepletlo s bránou merge); čip **Ke schválení: N** s tlačítkem **✓ Potvrdit návrhy (M)**, které jedním zápisem potvrdí návrhy uzavření od agentů s hotovými důkazy bez N/A (bez návrhů vypnuté „Potvrdit návrhy (0)“, chyba serveru zůstane v panelu); vráceno po #30, viz `editor/canvas/sector-proposals` | tváře karet vrstvy, `done` + `evidence` z desktop-v3 stavu, `POST /api/desktop-v3/confirm-proposals` |
| **Vazby `next`** | Z hotové karty (`card_closed` / `plan_written_back`) plná zelená, jinak přerušovaná. Uložení, které by uzavřelo cyklus, vrátí 409 `card_cycle`; lišta chyb vypíše cestu jmény karet a nic se neuloží | `cards[]`, `POST /api/graph` |
| **Velín** | Filtry Vše / Na tebe / Problémy / Běží; projekt (složený pruh tónů a počty) → vrstva → sektor → pilulky karet podle `topoIndex`; vpravo nejvýš 3 rozhodnutí pro tebe a 5 dalších připravených akcí; „Teď běží“ s agentem, krokem, postupem a odpočtem lease (prošlý červeně s ✕). Klik otevře detail karty | agent-state |
| **Živý pás** | Sbalený: poslední 4 události `čas značka karta · co`. Rozbalená Časová osa (5 / 15 / 60 min): dráha = karta vrstvy v pořadí `topoIndex`, značky událostí, pás pronájmu (claim → výsledek/vypršení/teď), čárky heartbeatu, čára „teď“; vpravo posledních 30 událostí. Klik otevře detail karty na záložce podle druhu události. Na telefonu jen seznam | `GET /api/oporahub/events`, SSE `…/events/stream` |

**Jeden klient událostí** (`frontend/editor/live-strip/logic/events-client.ts`): na prostor jedno spojení sdílené všemi
odběrateli. Start: `head`, posledních až 200 událostí, pak SSE od kurzoru. Po chybě spojení dočte
`/events?since=<kurzor>` (pozná `gap`) a připojí se znovu; po třech selháních zůstane u pollingu po 5 s.
Nová událost nebo `gap` po 400 ms znovu načte agent-state (sdílený poller), takže tváře karet, Velín i pás
drží snímek + deltu. **Detail karty** se otevírá jen přes `openCardDrawer(nodeId, tab?)`
(`frontend/hub/oporahub-card-drawer/open.ts`); stejné API jako drawer W3b (`oporahub/card-drawer`), který soubor při sloučení nahradí; do té doby App otevře kartu v OporaHubu.

## Zdraví, tvar a role

| `health` | Tón | Značka | Vzhled |
|---|---|---|---|
| `ok` | zelená | ✓ | plný horní pruh |
| `waiting` | zlatá | ◷ | plný horní pruh |
| `blocking` | červená | ✕ | červený rámeček |
| `not_connected` | šedá | ◌ | přerušovaný rámeček, spojka přerušovaná „nenapojeno“ |

Barva nikdy nenese význam sama: vždy značka a slovo. Kroky člověka (přijetí, review, merge) mají
zlatý zaoblený štítek, kroky agenta (převzetí, práce, důkazy, PR) tyrkysový hranatý. Strojový
`reason` se překládá do češtiny; neznámý kód se zobrazí doslova.

## Data a obnova

- Jediné periodické čtení agent-state: `useAgentState` nad sdíleným `agentStateStore`
  (`frontend/hub/oporahub-agent-state/logic/agent-state-store.ts`): přehled OporaHubu i odznaky na plátně odebírají
  **jeden** poller na prostor (10 s po dokončení čtení, jen ve viditelném okně); poslední odběratel ho
  zastaví. Posílá `If-None-Match`; `304` jen potvrdí čerstvost snímku.
- Detaily vlny 5 (brána, důkazy, historie, konflikty, metriky, kniha, identity) čtou jednou při otevření
  a po „Obnovit“ (`frontend/hub/oporahub-mirror/logic/use-hub-read.ts`); nic z nich nepolluje.
- Starší hooky zůstávají pro detaily, které agent-state nenese (řetěz změnových sad karty, běhy,
  rozpočet, obsah). Periodická čtení změn obsahu, formálních podkladů, sledování GitHubu a review
  návrhů běží jen s otevřeným detailem (`onDetailOpenChange` → `App`).
- Parser odmítne dokument jiného projektu/prostoru, neúplnou smyčku a neznámé zdraví.

## Kontrakt `data-oh-*` (DOM pro agenty)

Agent nečte obrazovku. Čte buď JSON zrcadlo, nebo atributy:

```js
JSON.parse(document.getElementById("oh-agent-state").textContent) // celý dokument agent-state
document.querySelectorAll('[data-oh-action-status="ready"]')      // připravené akce
```

| Prvek | Atributy | JSON cesta |
|---|---|---|
| Kořen | `data-oh-view` (`overview`/`agent`), `data-oh-accepted-head`, `data-oh-etag`, `data-oh-generated-at`, `data-oh-schema-version` | `heads.acceptedHead`, `generatedAt` |
| Zrcadlo | `<script type="application/json" id="oh-agent-state">` (`<` escapováno jako `<`) | celý dokument |
| Dlaždice | `data-oh-field` (`acceptedHead`, `drift`, `staleProposals`, `riskMix`, `decisions`) + `data-oh-value` | `heads.*`, `riskMix`, `decisions.length` |
| Etapa | `data-oh-stage`, `data-oh-health`, `data-oh-reason`, `data-oh-count` | `stages[]` |
| Spojka | `data-oh-link="from->to"`, `data-oh-link-state` (`plain`/`warn`/`broken`) | odvozeno |
| Rozhodnutí | `data-oh-decision`, `data-oh-action-id` | `decisions[]` |
| Akce | `data-oh-action-id`, `data-oh-action-status`, `data-oh-verb`, `data-oh-method`, `data-oh-path`, `data-oh-target`, `data-oh-block-reason` | `actions[]` |
| Fakt CAS | `data-oh-field` + `data-oh-value` (`acceptedHead`, `graphDigest`, `contextVersion`, `workingDiffers`, `budgetPolicyHead`) | `heads.*` |
| Mezera | `data-oh-gap`, `data-oh-health="not_connected"` | `gaps[]` |
| Detail karty | kořen `data-oh-view="card-drawer"`, `data-oh-node-id`, `data-oh-tab`, `data-oh-stage`, `data-oh-health`, `data-oh-accepted-head`, `data-oh-execution`; ✕ `data-oh-close="card-drawer"`; záložky `data-oh-tab`; stav `data-oh-field="status"` + `data-oh-reason`; dílky hotovo `data-oh-dod` + `data-oh-dod-state` (`done`/`active`/`todo`/`unknown`), `data-oh-dod-source` (`backend`/`computed`); patička `data-oh-next-action`, `data-oh-verb`, `data-oh-action-status`, `data-oh-actor`, `data-oh-block-reason`; zrcadlo `script#oh-card-drawer` (karta, stav, hotovo, další akce, kroky, běh, brána) | `cards[]`, `actions[]` |
| Detail · Zadání | `data-oh-view="card-spec"`, `data-oh-spec-mode`, `data-oh-spec-field` + `data-oh-diff`, `data-oh-line`, `data-oh-step-diff`, `data-oh-changeset` + `data-oh-parent` + `data-oh-stale` + `data-oh-risk`, `data-oh-conflicts`, `data-oh-propose`, `data-oh-working-changes` | `…/changesets/context`, `…/changesets` |
| Detail · Kroky | `data-oh-view="card-steps"`, `data-oh-steps-total`/`-done`/`-current`/`-source`; krok `data-oh-plan-step`, `data-oh-step-status`, `data-oh-step-current`, `data-oh-depends-on`, `data-oh-order`, `data-oh-step-acceptance` + `data-oh-met`, `data-oh-step-evidence` | `fields.steps`, `stepResults` |
| Detail · Běh | `data-oh-view="card-run"`, `data-oh-execution`, `data-oh-epoch`, `data-oh-execution-state`, `data-oh-lease-state`, `data-oh-lease-remaining`; `data-oh-field` (`lease-countdown`, `lease-holder`, `assignment`) + `data-oh-value`; `data-oh-budget`, `data-oh-step-result` + `data-oh-step-status`, `data-oh-self-check` | `…/executions`, `…/execution-budgets` |
| Detail · Review & PR | `data-oh-view="card-review"`, `data-oh-pr-number`, `data-oh-head-sha`, `data-oh-gate-status`, `data-oh-gate-rule`, `data-oh-pr-link`, `data-oh-pr-state`, `data-oh-freshness`, `data-oh-gate-reason` + `data-oh-rule-state`, `data-oh-finding` + `data-oh-severity` + `data-oh-finding-status`, `data-oh-approvals-*`, `data-oh-identity` | `…/review-jobs/gates`, `…/review-jobs` |
| Detail · Historie | `data-oh-view="card-events"`, `data-oh-events-head`, `-count`, `-truncated`, `-filter="client"`; událost `data-oh-event`, `data-oh-event-kind`, `data-oh-step`, `data-oh-execution` | `…/events` |
| Pata | `data-oh-detail` (druh původního detailu) | — |
| Etapa Review / Návrh | `data-oh-gate-status` (`blocked`/`pending`/`clear`/`off`), `data-oh-gate-rule`; `data-oh-conflicts` | `stages[review]`, `actions[verb=proposal.resolve_conflict]` |
| Akce (doplněk) | `data-oh-group`, `data-oh-attention` | `actions[].verb`, `.attention` |
| Tvář karty | `data-oh-card-face` (nodeId), `data-oh-face-state` (`blocked`/`ready`/`working`/`review`/`decision`/`done`/`problem`/`plan`), `data-oh-stage`, `data-oh-health`, `data-oh-reason`, `data-oh-execution`, `data-oh-steps-total`, `data-oh-steps-done`, `data-oh-lease-holder`, `data-oh-lease-epoch`, `data-oh-lease-expires`; patička `data-oh-gate-status` + `data-oh-gate-rule` / `data-oh-blocked-by` / `data-oh-decision` + `data-oh-action-id`; hlava vrstvy `data-oh-view="layer-summary"` + `data-oh-tone`/`data-oh-value`; zrcadlo `script#oh-card-stages` | `cards[]`, `decisions[]` |
| Velín | `data-oh-view="velin"` + `data-oh-etag`; `data-oh-layer`, `data-oh-sector`, pilulka `data-oh-node-id` + `data-oh-tone` + `data-oh-stage` + `data-oh-reason`; `data-oh-decision`, `data-oh-action-id`, `data-oh-verb`; Teď běží `data-oh-lease-holder`, `data-oh-lease-expires`; zrcadlo `script#oh-velin` | agent-state |
| Živý pás | `data-oh-view="live-strip"`, `data-oh-transport` (`connecting`/`sse`/`poll`), `data-oh-cursor`; `data-oh-lane` (nodeId), `data-oh-event` (id) + `data-oh-kind` | `…/events`, `…/events/stream` |
| Krok Review karty | `data-oh-step="review"`, `data-oh-card-stage`; panel `data-oh-review-gate` (executionId), `data-oh-gate-status`, `data-oh-gate-rule`, `data-oh-gate-reason`, `data-oh-open-important`, `data-oh-security`, `data-oh-approvals-required`, `data-oh-approvals-verified`, `data-oh-humans-mode`, `data-oh-self-checks`, `data-oh-stale-against-main`, `data-oh-template-incomplete`; zrcadlo `script#oh-review-gates` | `…/review-jobs/gates` |
| Formální důkazy karty | `data-oh-proof-kind`, `data-oh-proof-status`, `data-oh-trust`, `data-oh-verification`; tlačítko `data-oh-verb="verification.fix"` + `data-oh-action-id`; zrcadlo `script#oh-card-proofs` | `…/verifications?nodeId` |
| Historie karty | `data-oh-view="card-history"`, `data-oh-history-revision`, `data-oh-proposal`, `data-oh-blame-key`, `data-oh-revision`; zrcadlo `script#oh-card-history` | `…/history/card`, `…/blame/card` |
| Konflikty | `data-oh-view="conflicts"`, `data-oh-conflict`, `data-oh-conflict-status`, `data-oh-proposal`, `data-oh-proposal-kind`, `data-oh-field-key`, `data-oh-choice`; zrcadlo `script#oh-auto-rebase-conflicts` | `…/auto-rebase/conflicts` |
| Lidé v review | `data-oh-view="identity"`, `data-oh-identity`, `data-oh-identity-state`, `data-oh-operator`, `data-oh-github-login`; zrcadlo `script#oh-review-identities` **bez `marker`** | `…/review-identities` |
| Metriky review | `data-oh-view="review-metrics"`, `data-oh-window`, `data-oh-metric` + `data-oh-value`; zrcadlo `script#oh-review-metrics` | `…/review-metrics`, `…/review-evals` |
| Kniha důkazů | `data-oh-view="proof-ledger"`, `data-oh-ledger-entry`, `data-oh-ledger-status`, `data-oh-trust`, `data-oh-metric` + `data-oh-value`; zrcadlo `script#oh-proof-ledger` | `…/verifications/ledger` |

Zdroj pravdy pro tabulku v aplikaci je `frontend/hub/oporahub-agents/logic/contract.ts`.
Atributy jsou jen ke čtení; každý zápis dál ověří původní API a akce `human_only` zůstávají člověku.

## Kód

`frontend/hub/oporahub-agent-state` (čtení a mapování, testy), `oporahub-loop` (Přehled),
`oporahub-card-drawer` (jednotný detail karty, testy view-modelů vedle `logic/`), `oporahub-agents` (Pro agenty),
`oporahub-health` (značky), `oporahub-overview` (rám, záložky, zrcadlo, pata, drawer),
`oporahub-workspace` (skládání, přímý odkaz `?ohView=agents`; `?ohCard=` čte detail karty sám).
Vlna 5: `oporahub-review-gate` (krok Review karty), `oporahub-proofs` (důkazy karty, kniha důkazů),
`oporahub-card-history`, `oporahub-conflicts`, `oporahub-review-metrics`, `oporahub-identity`,
`oporahub-mirror` (jednorázové čtení a zrcadla `oh-*`). Editor lean: `editor/canvas/card-face` (tvář, glyf,
hlava vrstvy, tóny), `frontend/editor/canvas/board/logic/dag-edges.ts` a `card-cycle.ts`, `editor/control-tower` (Velín),
`editor/live-strip` (klient událostí, dráhy), `editor/canvas/add-menu`, `ui-kit/toolbar-menu`,
`hub/oporahub-card-drawer` (šev detailu karty), `hub/review-lens` (plátno PR Lens), `hub/plan-lens` (Lens plánu).

## Ověření

`npm test` (mapování agent-state → view-model, parser, 304, escapování zrcadla, cesta karty,
kontrakt, vykreslení atributů), `npm run build` a screenshoty světlý/tmavý režim při 1440 a 390 px
nad lokálně naplněným backendem (`tools/serve-preview.py` na vlastním portu, nikdy 8740).
