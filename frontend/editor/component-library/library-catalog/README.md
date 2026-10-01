Katalog knihovny (levý navbar) jako **data**. Dlaždice mimo katalog neexistuje: panel `frontend/layout/library-navbar/` i budoucí drop na plátno berou obsah odsud a nic si nedomýšlejí.

Položka (`CatalogItem`) je know-how, ne obrázek:

- `id` — stabilní identita; jde v tažení přes `dataTransfer` a vrací se zpátky přes `itemById(id)`.
- `category` — jedna z devíti kategorií (`CatalogCategory`), které odpovídají blokům 2–10 sektoru „Drag&drop-knihovna-levý navbar“: `fe-components`, `fe-css`, `fe-logic`, `backend`, `database`, `cloud`, `cache`, `security`, `tests`.
- `label` / `hint` / `icon` — co uživatel vidí na dlaždici.
- `kind` — `card` (při puštění na plátno vznikne karta a bloky rozpadu) nebo `block` (jeden blok). Čte to fáze 3; panel podle toho nic neskrývá.
- `rules` — `must` / `mustNot`: co musí platit a čeho se držet dál.
- `decomposition` — kroky rozpadu: dílek, směr dat, kde bydlí stav.
- `template` — krátká kostra kódu v konvencích tohoto repozitáře.

Soubory v `logic/`:

- `library-catalog.ts` — typy, kategorie, složený `CATALOG_ITEMS` a čisté funkce: `itemsOf`, `itemById`, `searchItems`, `foldDiacritics`, `decompositionSummary`, `catalogLint`, konstanta `CATALOG_DRAG_TYPE`.
- `catalog-frontend-components.ts`, `catalog-frontend-style.ts`, `catalog-frontend-logic.ts`, `catalog-backend.ts` (backend + databáze), `catalog-platform.ts` (cloud + cache), `catalog-safety.ts` (security + testy) — jen data, rozdělená tak, aby žádný soubor nepřerostl.
- `catalog-insert.ts` — překlad položky na to, co po puštění stojí na plátně: `cardFromItem(item, parentId, x, y)` dá uzel grafu (jméno = `label`, účel = `hint` a za ním první řádek šablony, který je v katalogu odkazem na místo kódu), `workflowFromItem(item)` dá stav uzlu (rozpad jako očíslované bloky přes `renumber` z modelu stromu, na konci blok „Šablona“, `rules.must` / `mustNot` jako pravidla uzlu `must` / `must_not`), `blockFromItem(item)` dá jeden blok (nadpis = `label`, text = šablona, štítek = kategorie) a `insertBlockFromItem(nodeId, item)` je hotová mutace stavu postavená na `addBlock` + `updateBlock`. Pozici jen nese — o dosednutí mezi pevná tělesa se stará `settleCard` na plátně.
- `catalog-insert.test.ts` — testuje jméno i účel karty, odkaz na šablonu, číslování bloků, pořadí pravidel, štítek bloku a to, že druhé vložení do téže karty blok jen přidá a přečísluje.
- `library-catalog.test.ts` — testuje, že žádná kategorie není prázdná, že `id` jsou jedinečná, že každá položka nese pravidlo, rozpad i šablonu, že hledání najde „Formulář“ na dotaz „formular“ a že lint je nad vydaným katalogem prázdný a nad schválně špatnou položkou hlásí.
- `catalog-lint.test.ts` — trvalá brána: `catalogLint(CATALOG_ITEMS)` musí být `[]`, jinak test vypíše `itemId` a pravidlo každého porušení. Pod bránou jsou fixtury pravidlo po pravidle (px, vnoření, `!important`, `#id`, dvojité `__`) a kontrola, že každá položka `fe-css` zmiňuje v `rules.must` relativní jednotku.

`catalogLint` je pravidla bloku 3 zapsaná jako test: v šabloně smí být `px` jen na `border*` (kromě `border-radius`), `outline*`, `box-shadow` / `text-shadow`, na 1px lince a na ikoně do 24; všechno ostatní patří do `rem`, `em`, `%` nebo `fr`. Selektory se nesmí vnořit přes tři úrovně — ať vznikne vnoření skládáním pravidel do sebe (`.a { .b { .c { .d {`), nebo plochým potomkovským selektorem na jednom řádku (`.a .b .c .d {`). Žádné `!important` (přebíjí kaskádu), žádný `#id` selektor (BEM styluje přes třídu, ne přes identitu uzlu) a žádná třída s víc než jedním `__` v řadě (`.blok__prvek__prvek` řetězí prvek do prvku; BEM zná jen `blok__prvek`).

Katalog nezná projekt: nečte `sourceKind`, id projektu ani pracovní prostor. Je stejný pro všechny projekty.
