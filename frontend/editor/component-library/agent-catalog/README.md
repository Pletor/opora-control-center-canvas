Katalog pravého navbaru (knihovna postupů — JAK ovládat Clauda a agenty) jako **data**. Sdílí tvar
položky s levým navbarem (`frontend/editor/component-library/library-catalog/`): `rules`,
`decomposition`, `template` a čisté funkce `foldDiacritics`/`CatalogRules`/`CatalogStep` se odtud
**importují, ne kopírují**. Panel `frontend/layout/agent-navbar/` a drop na plátno (fáze 3 sektoru,
`agent-insert.ts`) berou obsah odsud a nic si nedomýšlí — dlaždice mimo katalog neexistuje.

## Co je jinak než u levého katalogu

Levý katalog nese know-how o kódu (`template` = kostra kódu, `kind: "card" | "block"` řídí, co na
plátně vznikne). Tenhle katalog nese know-how o **postupu**: `template` je číslovaný text (kroky),
a každá položka navíc nese `endCriteria` (kdy je postup u konce) a `stopCondition` (kdy se má agent
zastavit a zeptat, místo aby domýšlel) — to je jádro kontraktu karty pro agenty
(`docs/karta-pro-agenty.md`): agent musí vždy vědět, kdy skončit a kdy si říct o chybějící vstup.

## Tvar položky (`AgentItem`)

- `id` — stabilní identita; jde v tažení přes `dataTransfer` (typ `AGENT_DRAG_TYPE`) a vrací se
  zpátky přes `agentItemById(id)`.
- `category` — jedna z šesti kategorií (`AgentCategory`): `workflows`, `pipelines`, `rules`, `hooks`,
  `skills`, `agents`.
- `label` / `hint` / `icon` — co uživatel vidí na dlaždici.
- `kind` — co drop na plátno vytvoří (čte fáze 3 sektoru, `agent-insert.ts`, mimo tuto složku):
  `rule` → pravidlo uzlu, `action` → akce v bloku Akce, `workflow` → sektor s uzly podle fází
  (discover/define/build/verify/live) a vazbami `next`, `agent` → pravidlo uzlu s rolí a modelem,
  `info` → položka se nedá přetáhnout (jen orientace, např. kdy použít skill).
- `rules` — `must` / `mustNot`, stejný tvar jako v levém katalogu.
- `decomposition` — kroky rozpadu (`title`, `text`), stejný tvar jako v levém katalogu.
- `template` — **postup jako číslovaný text** (`"1. …\n2. …"`), ne kostra kódu. U `kind: "workflow"`
  musí jmenovat všech pět fází uzlu: `discover`, `define`, `build`, `verify`, `live` (`PHASES` v
  `backend/editor/agent_memory/desktop_v3_state.py`) — lint to hlídá.
- `endCriteria` — věta, podle které agent i člověk poznají úspěšný konec postupu.
- `stopCondition` — věta, kdy se má postup zastavit a vyžádat si chybějící vstup, místo domýšlení.
- `refs` — id položek levého katalogu (`CATALOG_ITEMS` z `library-catalog.ts`), na které krok
  pipeline odkazuje **odkazem, ne kopií textu**. Smí být prázdné pole; u kategorie `pipelines` musí
  mít aspoň jeden prvek (lint i test to vyžadují).

## Soubory v `logic/`

- `agent-catalog.ts` — typy, kategorie (`AGENT_CATEGORIES`), složený `AGENT_ITEMS` a čisté funkce:
  `agentItemsOf`, `agentItemById`, `searchAgentItems`, `agentCatalogLint`, `startAgentDrag`, konstanta
  `AGENT_DRAG_TYPE`.
- `catalog-workflows.ts`, `catalog-pipelines.ts`, `catalog-rules.ts`, `catalog-hooks.ts`,
  `catalog-skills.ts`, `catalog-agents.ts` — jen data, po jedné kategorii na soubor, aby žádný
  nepřerostl ~200 řádků.
- `agent-insert.ts` — překlad položky na to, co po puštění stojí na plátně (fáze 3): `ruleFromItem`,
  `actionFromItem`, `sectorFromWorkflow`, vložení do vybrané karty (`insertRulesFromItem`,
  `insertActionFromItem`) a pomůcky `phasesFromTemplate`, `phaseNote`, `PHASE_LABELS`, `PHASE_ORIGIN`,
  `PHASE_STEP`, `NEW_CARD_PHASE`. Čisté funkce bez Reactu a bez API; ukládá App.
- `agent-insert.test.ts` — testuje prefix popisku u pravidel, pravidlo s rolí u `kind: "agent"`, tvar
  akce a mezí parametrů, rozložení karet fází i vazby `next`, kritérium konce na poslední kartě,
  odmítnutí položky `info` a to, že druhé puštění téže dlaždice kartu nezaplevelí.
- `agent-catalog.test.ts` — testuje, že žádná kategorie není prázdná, id jsou jedinečná, každá
  položka nese pravidlo, rozpad, šablonu, kritérium konce a stop podmínku, že každá pipeline má
  aspoň jeden `ref`, že hledání je bez diakritiky, že `agentCatalogLint(AGENT_ITEMS)` je `[]` a že
  chytí schválně špatné položky (chybějící stop, chybějící konec, neznámý `ref`, workflow bez fází,
  prázdná šablona), a že `startAgentDrag` zapisuje jen id pod `AGENT_DRAG_TYPE` s `effectAllowed: "copy"`.

## Co drop na plátno udělá (`agent-insert.ts`)

Panel jen zvedne dlaždici (`startAgentDrag` pošle pod `AGENT_DRAG_TYPE` jen id); co z ní vznikne,
rozhoduje App podle `kind`. Plátno pošle nahoru `onAgentDrop(itemId, x, y)` a nic víc nezná.

| `kind` | Kam to jde | Co přesně vznikne |
|---|---|---|
| `rule` | pravidla vybrané karty | `ruleFromItem`: každé `must`/`mustNot` jako pravidlo uzlu, text s popiskem položky vepředu. |
| `agent` | pravidla vybrané karty | totéž a navíc **první** pravidlo `must` „Role: `<label>`. `<hint>`“ — role a model se čtou dřív než úkoly. |
| `action` | blok Akce vybrané karty | `actionFromItem`: `pipelineId` = id položky, parametry `steps` / `endCriteria` / `stopCondition` / `refs` jako texty (backend žádá objekt textů, viz `ACTION_KEYS` a `MAX_PARAMS`). |
| `workflow` | graf | `sectorFromWorkflow`: sektor se jménem postupu a uvnitř karta na každou fázi ze šablony (Objevit, Definovat, Postavit, Ověřit, Provoz) v řadě od `80,80` po `320`, spojená vazbami `next`; kritérium konce visí na poslední kartě. |
| `info` | nikam | všechny tři překlady vrací `null`; dlaždice se ani nedá zvednout. |

Bez vybrané karty se pravidlo, role ani pipeline nepustí (App řekne „Nejdřív vyberte kartu.“) a do
uzavřené karty (`done.confirmed`) se nepřidává nic. Totéž pravidlo (podle textu) ani tatáž pipeline
(podle `pipelineId`) se nepřidá dvakrát. Sektor jde do grafu jedinou cestou — přes `save` — takže ho
**Ctrl+Z vezme zpátky celý** i s kartami a vazbami; teprve nad hotovým sektorem jeden `desktop.mutate`
doplní stav nových karet.

Nová karta fáze stojí vždy na `discover`, i když zastupuje pozdější fázi: backend
(`check_phase_transitions` v `backend/editor/agent_memory/desktop_v3_state.py`) pustí kartu dál jen
s neprázdnými a splněnými kritérii, a čerstvě puštěná karta žádná nemá. Fáze, kterou karta zastupuje,
je proto vidět jejím jménem a pořadím vazeb `next`, ne předstíraným postupem.

## Jak přidat položku

1. Otevři soubor kategorie (`catalog-<kategorie>.ts`) a přidej objekt do pole — ne nový soubor, dokud
   se kategorie nevejde do ~200 řádků.
2. Vyplň všech jedenáct polí `AgentItem`; `id` musí být jedinečné napříč **celým** katalogem (test to
   hlídá nad `AGENT_ITEMS`, ne jen nad jedním souborem).
3. Pokud jde o `pipelines`, přidej aspoň jeden `refs` na existující id v `CATALOG_ITEMS` (levý
   katalog) — lint i test odmítnou neznámý odkaz nebo prázdné `refs`.
4. Pokud `kind: "workflow"`, ať `template` doslova obsahuje slova `discover`, `define`, `build`,
   `verify`, `live` (malými písmeny stačí, lint hledá case-insensitive přes `toLowerCase()`).
5. Spusť `npm test` — `agent-catalog.test.ts` i lint musí projít bez úprav testu.

## Pravidla linteru (`agentCatalogLint`)

Nad vydaným katalogem (`AGENT_ITEMS`) musí být `agentCatalogLint()` prázdné pole. Kontroluje čtyři
věci, každá se svým `rule` v nálezu:

| `rule` | Kdy se ohlásí |
|---|---|
| `end` | `endCriteria` je prázdné nebo jen bílé znaky. |
| `stop` | `stopCondition` je prázdné nebo jen bílé znaky. |
| `template` | `template` je prázdné, nebo `kind: "workflow"` a šabloně chybí některá z fází discover/define/build/verify/live. |
| `ref` | Některé id v `refs` neexistuje v `CATALOG_ITEMS` levého katalogu. |

Katalog nezná projekt: nečte `sourceKind`, id projektu ani pracovní prostor. Je stejný pro všechny
projekty a pro všechna prostředí (Editor i Live Run).
