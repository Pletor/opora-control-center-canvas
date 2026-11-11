# Plátno 3: folie skutečnosti, monitor karty a strom

Stav: kontrakt k odsouhlasení (2026-11-11). Navazuje na `2026-11-10-platno-2.md` (vize stránky), `karta-pro-agenty.md`,
`2026-10-22-plan-vs-realita.md` (§D bod 1 `plan_reality` – tady se staví) a `stopa-prace-karty.md`.
Ukázky člověkem odsouhlaseného směru: artefakty „Folie skutečnosti“, „Mapa růstu“ a „Živá karta OPORY“ (11. 11. 2026),
skica `image.png`.

## Proč

Plátno 2 drží **vizi srdce**: co se má dít a jaký je výsledek (oranžový obrys). Plátno 3 (Editor) je **plán Kanceláře**,
který roste. Přes něj se klade **folie skutečnosti**: co dělník opravdu postavil, odvozené z kódu, ne z jeho hlášení.
Srdce na folii vidí, co se děje, řeší jednu věc po druhé a milníky s funkčními výsledky posouvají projekt dál.
To je přidaná hodnota OPORY proti terminálu: plán, skutečnost a dohled v jednom obraze, vynucené kódem.

Barvy (ze skici člověka): oranžová = vize srdce, modrá = práce Kanceláře (pupen), zelená = doložený výsledek (list),
červená = slepá cesta. Folie: **shoda** (plán i kód), **chybí** (plán, kód ne), **navíc** (kód, plán ne = ujetí).

## Co už existuje a použije se (inventura 11. 11.)

- Kód ↔ karta: `Opora-Node` (`backend/canvas/commit_pairs.py`), `Opora-Mark` + `# OP-…` se symbolem
  (`backend/agi_pletor/linie/trace_git.py:49 code()`), `linie/trace.py` (gaps), echo `sync_signals.py`,
  `card_trail_judgment.py` (`files_mismatch`, `red_twice`, `delivered_without_evidence`), `plan_lens_code.py` (Graphify).
- Stopa karty `GET /api/oporahub/card-trail` (runs, kroky, soubory commitů), proud `/api/oporahub/events` + SSE,
  příjem z Kanceláře `POST /api/oporahub/process-events` (`tool.use {name, action, target}`, `turn.*`, `needs.input`).
- Hlídači: `determinism/triggers.py` (`stalled`, `retry`, `step_failed`…), milníky oblastí `determinism/milestones.py`,
  milníky prvku plátna 2 (`page_plan.py`, `plan-progress.ts`), `ProcessSync._status`.
- Kancelář (repo `agent-office`): háčky Claude → `claudeHook`, `failStreak`, diff worktree `changes.ts`,
  vložení textu do běžící relace `workers/manager.ts:525 prompt()`.

Pravidlo: nic z toho se nezdvojuje. Nový modul folie **nahradí** rozházené dílčí výpočty tam, kde dělají totéž
(`files_mismatch` se přesune do něj, echo a Lens plánu ho čtou), slepé uličky se mažou.

## F1: Folie z kódu (první milník)

**Očekávání karty** (co má v kódu být):
- `steps[].files` karty, cesty z `sourceRef`;
- u prvku z plátna 2 (`element.kind`) navíc pojmenované výsledky z jeho plátna logiky (`flow.outputs`, `dataTo`)
  a kritéria přijetí karty (`doneCriteria`); prvek plátna 2 tím dostane ověřitelná kritéria v Editoru.

**Skutečnost karty** (co v kódu je), deterministicky, bez modelu:
- commity karty (`commit_pairs` + `Opora-Mark`), jejich soubory a **symboly** (nové/změněné funkce, třídy,
  komponenty, routy FastAPI, testy) z rozdílu commitu – jen změněné soubory, parser podle přípony
  (Python `ast`, TS/TSX regex symbolů jako `trace_git.SYMBOL`); `# OP-…` značky přes `trace_git.code`;
- během běhu (bez commitu) poslední známý diff worktree z Kanceláře (F2), do té doby jen commity.

**Porovnání** `backend/canvas/plan_reality.py` (+ test): pro kartu `{matched[], missing[], extra[], symbols[],
evidence{commit, at}}`; položka `{kind: file|symbol|route|test|output, name, path, line?, source}`.
`extra` = soubor nebo symbol mimo očekávání karty (ujetí). Výsledek se počítá z gitu a grafu, ukládá se jen cache
klíčovaná SHA + revize karty.

**API**: `GET /api/oporahub/plan-reality?project&workspace&nodeId?` (bez `nodeId` souhrn vrstvy:
počty na kartu), čte člověk, srdce i dělník.

**Editor**: přepínač vrstvy **Záměr | Záměr + folie | Jen folie** (adresa `layer=`). Na kartě odškrtnuté
očekávání (✓ shoda / ○ chybí), pod kartou fixou co přibylo v kódu (jméno + soubor), oranžové čárkované „navíc“.
Dvojklik na položku fixy otevře soubor/řádek v náhledu kódu (existující code-intelligence / repo view).
Souhrn ve Velínu: kolik karet má ujetí.

**Hotovo když**: na projektu OPORA samotném (karty plátna 2 z větve platno2) folie ukáže skutečné symboly
commitů s `Opora-Mark: OP-9B197F`; cílené testy `plan_reality` (shoda/chybí/navíc, přejmenování, mazání,
cizí karta), `npm test`, `npm run build`.

## F2: Monitor karty a kryté záda

- **Kancelář posílá víc** (repo agent-office): `tool.use` nese změněné soubory (z `changes.ts`) a u testu
  výsledek; nová událost `worker.diff {files[], at}` při každé změně souborů (throttle 10 s).
- **Monitor karty** v Editoru (panel karty): živé kroky dělníka z `tool.use`, `turn.*`, počitadla shoda/chybí/navíc
  z F1, signály hlídače, zprávy srdce. Zdroj: proud událostí filtrovaný `nodeId` (žádné nové úložiště).
- **Hlídač bez modelu** (`determinism/triggers.py` rozšířit, ne nový modul): běží i podle času (tick 60 s),
  vidí `tool.use`. Signály: `stalled` (bez pokroku), `failing` (stejný test/nástroj selhal 3×, z `failStreak`),
  `drift` (soubor mimo očekávání karty = `extra` z F1), `needs.input`. Signál budí srdce (`wake_input`).
- **Srdce → běžící dělník**: nový druh brány `worker.message {ticketId, text, severity: hint|course|stop}`,
  jen role heart; Kancelář ho doručí do relace přes `manager.prompt()` a potvrdí `worker.message.delivered`.
  `stop` zastaví dělníka a vrátí kartu k přerozdělení. Zásahy jsou vidět v monitoru i v deníku karty.
- Rozhodnutí člověka (výchozí volby, mění Velín): ujetí vrací srdce samo (`course`), novou kartu jen navrhne.

## F3: Mapa růstu (forma Editoru, strom jen jako princip)

Člověk 11. 11.: samostatný obrázek stromu ne; princip růstu ano, ale ve formě karet a vazeb, do které se zapisuje
(artefakt „Mapa růstu“). Editor zůstává plátno karet, mění se uspořádání a tvář karty:
- **sloupce = milníky** zleva doprava k **cíli** (oblasti se sekvencí, `milestones.py`); hlavička sloupce nese
  funkční výsledek milníku (brána) a počet listů/karet; přetažení karty do sloupce ji přesune do milníku;
- **karta má tři vrstvy** (přepínatelné): **záměr** z prvku plátna 2 (oranžově, zapisovatelný), **plán** = kroky
  karty s ✓/○ podle F1, **folie** = co je v kódu (fixa, „navíc“ červeně); u běžící práce řádek monitoru (F2);
- **stav = tvar karty**: semínko (čárkovaný oranžový, jen záměr), pupen (modrý, Kancelář staví), list (zelený,
  doloženo), suchá (červená, slepá cesta, ztlumená); **návrh srdce** = fialová čárkovaná karta s Přijmout/Zahodit;
- **vazby s významem** vyžaduje / používá / dokládá (barva podle významu), tvoří se z portu karty jako dnes;
- **pás srdce** nad plochou: víra (cíl z plátna 2), **teď řeší** jednu věc (zvýrazněná karta) a fronta.
Stav karty se odvozuje (ProcessSync + F1 + exekuce), člověk zapisuje záměr, název, vazby a milník.

## Karta: živá, fraktální, pro agenty (rozhovor 11. 11.)

Ukázka: artefakt „Živá karta OPORY“. Rozhodnutí člověka z rozhovoru:

- **Fraktál**: nekonečné zanoření Cíl → Schopnost → Úkol; list = jeden úkol = jedna větev/PR (jména jako ve vývoji).
  Vazby mezi úrovněmi jsou **teleporty**: typované (vyžaduje / používá / dokládá / sdílí kód), živé (nesou stav cíle),
  ty z kódu (importy, sdílené moduly) vznikají samy a jsou čárkované.
- **Čtyři pravdy vedle sebe**: **Záměr** (srdce, z plátna 2, kritéria), **Zrcadlo kódu** (Kancelář, větev, živě = F1),
  **Skutečnost** (main / nasazeno teď), **Budoucnost** (co udělá sloučení: rozbité testy sousedů přes teleporty).
  Kód je pravda, záměr je soudce: při rozporu rozhoduje srdce. Kolize v budoucnosti blokuje sloučení, řeší srdce.
- **Procesy, ze kterých karta vychází**: tok dat (z plátna logiky), uživatelská cesta (kterou část obsluhuje),
  proces vývoje (Linie: Návrh → … → Nasazení, ticket, větev, PR, náhled), rozhodnutí a výzkum (fakta, varianty).
- **Tvář**: kruh postupu, stav + další krok, kritéria a zrcadlo s pruhy, rizika a kolize, poslední zásah srdce,
  počitadla (události, testy, cena), živé dráhy aktérů (dělník, hlídač, srdce, triggery) a tail deníku.
- **Kdo píše**: fakta jen háčky a deterministické nástroje (commit → zrcadlo, testy → kritéria, háček Kanceláře,
  změna souseda, změna záměru, hlídač zaseknutí/ujetí). Agent zapisuje jen úsudek (rámec, rozhodnutí, předávka).
- **Čtení pro agenty**: vrstvy podle hloubky na adrese `opora://card/<id>#souhrn|tvar|proces|denik?since=`
  (≈ 40 / 700 / 2 000 tokenů); úsudek přes srdce jako mentora tunelem OPORA ↔ Kancelář; agent s agentem jen
  adresovanou zprávou na vazbě.
- **Historie**: append-only deník událostí + aktuální projekce (časová osa); musí unést statisíce zápisů
  (deník po kartách, projekce se přepočítá, čtení `since=`).

Karta se staví postupně s milníky: F1 dodá Zrcadlo a Skutečnost, F2 živý běh, deník a zásahy srdce,
F3 uspořádání a teleporty; Budoucnost (dopad sloučení přes teleporty) je samostatný milník F4 po F2.

## Detail karty z reálných dat (inventura 11. 11. večer)

Karta na plátně je malá tvář, dvojklik otevře **detail na 3/4 obrazovky**: rozšíření existujícího
`hub/oporahub-card-drawer` (záložky `CARD_TABS`, URL `ohCard/ohTab`, dnes 600 / 1240 px), ne nový modal.
Záložka se ukáže jen, když pro kartu existují data. Co se plní hned z existujícího:

| Záložka | Zdroj (existuje) |
|---|---|
| Přehled | `agent-state` cards[] (tvář, gauge, gaps), `card-trail` (now, runs, kroky, checks, pr, judgment) |
| Výstup | `page-plan/scan/{id}/capture/*` (stránka, výřezy boxů), `/api/site-admin` tokeny, `DesignPage`/`LayoutCanvas`, storyboard, náhled Linie (port) |
| Logika | tok prvku z plátna 2 (`page-plan` logic + flow), `FlowCanvas` jen ke čtení |
| Linie | `/api/pletor/linie/trace/{mark}` (commity, code, checks, přijetí, merge, gaps), `evaluate` osy, `diff`, log náhledu |
| Běh | `/api/oporahub/events/stream?nodeId` (SSE, živě), `activity-log`, `executions/{id}/results` |
| Vazby | `GraphEdge` (relation, carries), `EdgeReportPanel`, `agent-messages` |

Chybí a staví se: cena na kartu (`card_gauge.attach` nepředává `cost`, `card.over_budget` nikdy nevystřelí),
příznaky `judgment` nejdou do srdce, `plan_reality` (F1), `turn.*` a `worker.message` (F2), teleporty
(`GraphEdge.relation` rozšířit o vyžaduje/používá/dokládá/sdílí kód), budoucnost (F4), retence `opora_events`
vs. deník statisíců zápisů.

**Srdce staví plátno 3** z plátna 2: milníky prvků → sloupce; prvek (box/logika) → karta schopnosti
s kritérii z `flow.outputs`; `flow.dataTo` → vazba „používá“; Kancelář při převzetí → úkol = ticket Linie
(potomek). Vazby „sdílí kód“ přidá determinismus z commitů/importů. Srdce zapisuje branou (`change`),
člověk vidí návrhy fialově a může vrátit.

**Rozhodnutí člověka 11. 11. (artefakt „Plátno 3 OPORY“ v2)**: plátno zůstává volné (React Flow), na něm
**procesy** = rámy s chronologií milníků (oblasti) k cíli; procesů může být víc, zanořené v kartě (sbalený rám
s vazbou „zanořeno“) nebo v jiné větvi. Detail karty = **živá karta** (líc pro člověka: teleporty, čtyři pravdy,
tok dat / výstup, Linie, testy a cena, živý běh, deník, rozhodnutí, potomci). **Přepínač vedle křížku** kartu
otočí na **rub pro agenty**: adresa `opora://card/<mark>`, lease, `#souhrn`/`#tvar` jako JSON, tabulka čtení po
vrstvách (metoda, adresa, velikost, existuje/nové), tabulka zápisu s rolí, spouštěče, syrový proud, nástroje.
Rub i líc čtou stejná data; `node-brief` dostane `layer=souhrn|tvar`.

**Pořadí karty**: K1 detail 3/4 + záložky z existujících dat + cena na kartu → F1 zrcadlo kódu → F2 živý běh
a zásahy srdce → F3 mapa růstu a stavba srdcem → F4 budoucnost.

## Pořadí a linie

Každý milník = vlastní kulička Linie, větev z `feat/velin-linie-platno2` (vlak), po milníku zastavení a přijetí
člověkem. F2 má dvě části (agent-office + canvas) – v Kanceláři se mění jen odesílání a doručení.
Měřítko přidané hodnoty po F2: eval terminál vs. OPORA (`backend/brain/evals/opora-vs-bare`).

## Otevřené otázky pro člověka

1. Fixa: funkce a soubory (F1 návrh), nebo hrubší schopnosti? (Návrh: funkce/soubory, schopnosti = výstupy prvku.)
2. Monitor: panel karty vpravo (návrh), nebo přímo na kartě na plátně?
3. Ujetí: srdce vrací samo (návrh), nebo se nejdřív ptá člověka?

## K1: kontrakt živé karty (ticket OP-E9B87D, větev feat/velin-linie-platno2-karta)

Ukázka, ke které se stavba blíží: artefakty „Živá karta OPORY“ (líc) a „Plátno 3 OPORY“ v2 (plátno, 3/4 detail, rub).

### Backend: `GET /api/oporahub/live-card?project&workspace&nodeId`

Modul `backend/canvas/live_card.py` (+ `test_live_card.py`), router v `backend/api/editor/`. Jen skládá existující
čtení (card-trail, agent-state, node-brief, TicketStore, linie trace, page-plan, executions), nic nového neukládá.
Každá sekce je `null`, když pro kartu nejsou data; frontend pak sekci nevykreslí. Každá sekce nese `source`
(adresa endpointu, ze kterého pochází), ať rub karty ukáže pravdu.

```
{
  nodeId, title, kind, crumbs: [str], state: "seed|bud|leaf|dry|prop|goal", progress: 0..100 | null,
  pills: [{text, tone: "work|real|risk|heart|vision"}],
  truths: {
    vision:  {source, items: [{text, status: "ok|miss|bad|wait"}]} | null,      # kritéria/záměr karty
    mirror:  {available: false, milestone: "F1"},                                # do F1
    reality: {source, items: [...], sha?: str} | null,                            # sloučeno v main / done_state
    future:  {available: false, milestone: "F4"}
  },
  edges: [{edgeId, dir: "in|out", relation: str|null, carries: str|null, other: {nodeId, title, state}, last: str|null}],
  flow:   {source, pageId, elementId, name, inputs, steps, outputs, conditions, dataTo} | null,
  output: {source, captures: [{label, url}], preview: {url, status} | null} | null,
  linie:  {source, ticketId, mark, branch, pr, axes: [{name, state, text}], commits: [{sha7, title}], gaps: [str]} | null,
  runs:   [{executionId, at, state, tests: {passed, total} | null, costUsd: number | null}],
  cost:   {totalUsd: number | null, budgetUsd: number | null},
  recent: [{at, actor, kind, text, source}],              # nejnovější první, ≤ 30
  decisions: [{text, source}],
  children: [{nodeId, title, state, progress}],
  next: {text, why} | null,
  heart: {at, severity, text} | null,
  agent: {
    address: "opora://card/<mark|nodeId>", lease: {holder, until} | null, revision,
    reads:  [{layer, method: "GET|SSE", url, size, exists: bool}],
    writes: [{role, method, url, what}],
    triggers: [{when, then}]
  }
}
```

Doplněk: `GET /api/desktop-v3/node-brief?…&layer=souhrn|tvar` (souhrn ≈ 40 tok: id, title, state, progress,
next, blocked, truths; tvar ≈ 700 tok: criteria, edges, children). Bez `layer` beze změny.
Cena: `card_gauge.attach` předá cenu běhů karty, `costUsd` přestane být vždy null a `card.over_budget` může vystřelit.

### Frontend: `frontend/editor/canvas/live-card/`

Rodič `LiveCard` drží data (`use-live-card.ts`: fetch live-card + SSE `/api/oporahub/events/stream?nodeId`
do `recent`), dílky dostávají props. Otevírá se dvojklikem na kartu (URL `ohCard`, existující
`card-drawer-store`), šířka `min(76vw, 1240px)`, výška `min(88vh, 920px)`, plátno zůstává za ním.
Líc: hlavička (kruh, drobečky, štítky, počitadla testy/USD), teleporty, čtyři pravdy (mirror a future šedé
„staví se F1/F4“), tok dat / výstup, Linie, řady testů a ceny, živý běh (dráhy + deník), rozhodnutí, potomci,
patička s dalším krokem. Rub (přepínač „Pro člověka | Pro agenty“ vedle křížku, otočení): adresa, lease,
`#souhrn`/`#tvar` JSON (z node-brief `layer`), tabulka čtení, tabulka zápisu, spouštěče, syrový proud, nástroje.
Stávající záložky draweru (spec, steps, lens, run, review, history) zůstanou dostupné z rubu jako „Pracovní panel“.

### Plátno

Tvář karty: kruh postupu, čtyři tečky Z/K/S/B, živý pulz při běžícím dělníkovi. Vazby: `relation`
vyžaduje / používá / dokládá / sdílí kód (barva, popisek, čárkovaně sdílí kód), volba při tažení z portu.
Oblasti (AreaCard) nesou milník a ukazatel postupu.

## F2: kontrakt monitoru (ticket OP-3DAFF9, větev feat/velin-linie-platno2-karta-folie-monitor)

Zásah srdce jde existujícím kanálem zpětné vazby ticketu (`ticket.feedback` / `ticket.answer`), ne novou cestou:
- **Brána**: nový druh `ticket.direct` (jen role heart) `{ticketId, severity: "hint"|"course"|"stop", text ≤ 2000}`.
  Přidá do zpětné vazby ticketu položku `{feedbackId, kind: "heart.<severity>", text, answer: null, from: "heart", at}`
  a vydá událost `worker.message {ticketId, feedbackId, severity, text}` s `nodeId = machine.cardId` (deník karty).
- **Kancelář** (repo agent-office, vlastní větev a PR): při synchronizaci zpětné vazby ticketu běžícího dělníka
  doručí každou novou položku `heart.*` jednou do relace (`manager.prompt`), `heart.stop` přes existující
  `execution-stop`; potvrdí procesní událostí `worker.message.delivered {ticketId, feedbackId, severity}` s `nodeId`
  a `executionId`. `tool.use` u editace nese cestu souboru (`target`).
- **Hlídač bez modelu** (`determinism/triggers.py`, žádné nové vlákno): při každé přijaté procesní události karty
  a v existující periodické smyčce srdce vyhodnotí `card.stalled` (bez pokroku), `card.failing` (stejný nástroj/test
  selhal 3× v řadě) a `card.drift` (editace souboru mimo očekávání karty podle `plan_reality.outside`; karta bez
  očekávání drift nemá). Signál budí srdce jako ostatní `card.*`.
- **Živá karta**: deník a dráhy aktérů ukazují `tool.use`, `worker.message`, `worker.message.delivered` a signály
  hlídače; rub uvádí `ticket.direct` mezi zápisy srdce.
- Omezení: dělník bez ticketu brány (jen lease karty) zprávu nedostane.

## F4: kontrakt budoucnosti (ticket z větve …-karta-folie-monitor-stavba-budoucnost)

Čtvrtá pravda karty říká, co udělá sloučení její otevřené práce. Počítá se bez modelu z gitu a vazeb, jen z paměti
podle hlav (cache klíčem `(targetSha, headSha)`), nikdy nespouští testy sousedů.

- **Modul** `backend/canvas/plan_future.py`: pro kartu vezme otevřené (nesloučené a Linií neblokované, `work.blocked`) úkoly Linie s `cardId` karty
  (`branch`, cíl = `baseBranch`, `headSha`). Pro každý:
  - `changed`: `git diff --name-only <cíl>...<hlava>`;
  - `conflicts`: `git merge-tree --write-tree --name-only <cíl> <hlava>` (git ≥ 2.38); nečistý výsledek = soubory
    v konfliktu. Je to jediný objektivní blok: takové sloučení stejně neprojde, srdce ho musí vyřešit;
  - `impacts`: sousední karty přes vazby plátna (obě strany, všechny `relation`) a karty se zrcadlem (F1, jen
    z paměti), ale jen se společnými soubory: průnik `changed` se zrcadlem souseda nebo s `changed` jeho vlastní
    otevřené práce → `{nodeId, name, via: relation|"shares_code", paths}`, `paths` nikdy prázdné; soused přes
    vazbu bez průniku se nepočítá;
  - `overlaps`: jiné otevřené úkoly (i jiných karet), které mění stejné soubory → varování, ne blok
    (ve vlaku sdílí soubory skoro každá větev, šum).
  - Verdikt karty: `blocked` (konflikt) > `warning` (dopady nebo překryvy) > `clean`.
- **Živá karta**: `truths.future = {available: true, verdict, works: [{mark, branch, target, changed, conflicts,
  impacts, overlaps}]}`; bez otevřené práce s `cardId` se sekce neukáže (`available: false`). Tečka B na tváři
  karty bere verdikt.
- **Hlídač**: `card.collision` (determinism/triggers, vedle `card.drift`) při konfliktu merge-tree (`blocked`), nebo
  když dopad zasáhne kartu, jejíž vlastní otevřená práce má s touto společné soubory (průnik `changed`); bez
  společných souborů nic. Budí srdce, signál `card.signal` do deníku karty.
- **Mimo F4** (odloženo, řekne zpráva): blokování `linie.py merge` při překryvu bez konfliktu; běh testů sousedů.
