# Plátno stránky (layout a logika)

Střed plátna 2 (`docs/navrhy/2026-11-10-platno-2.md`): stránka jako drátový model na 12sloupcové mřížce s čárkovanými vodítky.

- **Žádné překryvy**: sourozenci (boxy se stejným `parent`) se nikdy nepřekrývají a rodič pod řádkem hlavičky pojme všechny děti (`logic/settle-layout.ts`, `settleLayout`). Usazuje se každý zápis struktury (úpravy na plátně, šablony, Detail boxu přes `PageEditor.layout`, převzetí skenu přes `layoutOfProposal`, náhled skenu v `normalizeProposalSections`). Uložená data s překryvy se kreslí usazená bez zápisu a usazená se uloží při další úpravě struktury; zápis obsahu (inspirace boxu) vychází z uložených boxů, aby pod zámkem obsahu neměnil strukturu.
- **Magnet a stín dopadu**: při tahu i změně velikosti se hrana boxu blíž než jedna buňka přitáhne k hraně souseda nebo rodiče (`logic/magnet.ts`, počítá s necelou polohou pod ukazatelem), jinak se zaokrouhlí. Tažený, zvětšený i z palety puštěný box zůstane, kam ho člověk dal, a kolidující sourozenci uhnou dolů. Během tahu plátno kreslí výsledek puštění stejnými funkcemi jako zápis (`moveBox` / `resizeBox`): sourozenci už stojí tam, kam uhnou, a čárkovaný stín (`layout-canvas__shadow`) ukáže buňky dopadu, i ve vnořené mřížce.
- **Mezery a čitelnost**: mřížka má mezeru 8 px vodorovně i svisle (`GAP_PX`, CSS `--layout-gap`), papír vlastní okraj, vnořená mřížka odsazení od okraje rodiče a pod hlavičkou (okraj, ne padding: `cellAt` čte obdélník mřížky). Box obsah ořízne: název a role končí výpustkou (plný název v titulku), funkčnost a vzhled nejvýš tři řádky. Ve vrstvě Logika se štítky zalamují, kolik jich box pojme (`logic/chip-fit.ts`, odhad z šířky), zbytek ukáže „+N“ s názvy v titulku; box s vnořenými boxy nebo nízký box nese štítky v řádku hlavičky.

- **Vrstva 1 Layout**: box = sekce stránky (`site.sections[]`) s `box {x, y, w, h}` uvnitř rodiče a nepovinným `parent`. Box jde chytit a táhnout (posun, puštění nad jiným boxem ho vnoří, nad stránkou vynoří), úchytem vpravo dole změnit velikost, ✕ odebrat i s vnořenými boxy. V boxu je jen počet prvků logiky.
- **Pohled Layout | Design** vrstvy 1 (`look`, přepínač a pruh Design webu v `../design-look/`): v Layoutu box pod hlavičkou ukáže funkčnost (`intent`); text má jen box bez vnořených boxů a aspoň dva řádky vysoký. V Designu plátno místo mřížky vykreslí `../design-page/` (stránka v celku z celých výřezů boxů `covers`, bez tahu).
- **Vrstva 2 Logika**: boxy jsou cíle (`data-drop-section`), nad papírem pruh **Celá stránka**. Prvek je štítek `LogicChip` (symbol, druh, název, milníky); klik vybere, dvojklik otevře plátno logiky prvku (chybějící založí prázdné, `onOpenLogic` z `project-flows`), ✕ odebere, tah (`onCarry`) přesune, ⚙ (i převzetí z knihovny) (`project-flows/LogicFlowButton`, plné = prvek má plátno logiky) nastaví logiku na plátně toku.

- **Výběr boxu**: klik na box mimo tlačítka a štítky ho vybere (`onSelectBox`, vnořený box vyhraje), vybraný box svítí akcentem (`selectedBox`). **Dvojklik na box** (obě vrstvy, mimo tlačítka a štítky, vnořený vyhraje) ho otevře v zanořeném pohledu (`onOpenBox`, `../box-focus/`). Přejmenování je v Detailu boxu. **Značky** v hlavičce boxu (`logic/box-badges.ts`): Návrh, skica ✎ (`sketches`), počet inspirací, ve vrstvě Layout počet prvků s nejhorším milníkem, Ověřeno. Box `proposed` má čárkovaný rám.
- **Náhled** (`preview`): totéž vykreslení jen ke čtení pro panel skenu, bez `data-grid-parent` / `data-drop-section`, výběru a test id, aby tah z palety nikdy nemířil do cizího layoutu.

Dílek drží jen náhled tahu boxu (včetně layoutu po puštění); změnu hlásí jednou při puštění `onLayout(sections)` (přesně to, co ukázal stín). Ukládá `ArchitectureEditor`.

- `components/LayoutCanvas.tsx` (rekurzivní mřížka, tah boxu s magnetem a stínem dopadu; ukazatel zachytí až první pohyb nad 4 px, aby klik a dvojklik na box zůstaly obyčejné; tažený box se kreslí ve své mřížce, aby přemístění nezrušilo zachycení ukazatele), `components/LayoutBox.tsx`, `components/LogicChip.tsx`.
- `logic/layout-grid.ts` (test vedle): `clampBox`, `settle` (kolize jednoho boxu: sjede pod souseda), `endBox` (na konec), `cellAt` (buňka pod ukazatelem s mezerou), `layoutSections` (starší sekce bez `box` pod sebe na celou šířku, neplatný rodič pryč), `canNest` (bez cyklu, hloubka ≤ 3), `ROW_PX = 32`, `GAP_PX = 8`, `ROW_PITCH`, `columnPitch`.
- `logic/settle-layout.ts` (test vedle): `settleLayout(sections, first?)` usazení celého layoutu, idempotentní, mění jen `box`; `first` = box s předností.
- `logic/magnet.ts` (test vedle): `magnet(box, sourozenci, "move" | "resize")`.
- `logic/chip-fit.ts` (test vedle): `chipFit` kolik štítků se vejde a zda do hlavičky.
- `logic/layout-edit.ts` (test vedle): `addBox`, `moveBox`, `resizeBox` (každá usadí layout s předností upraveného boxu), `removeBox`, `newSectionId`.
- `logic/layout-templates.ts` (test v `layout-edit.test.ts`): `BOX_KINDS`, `TEMPLATES` (Klasický web, Landing, Aplikace), `templateSections` (id volná vůči dosavadním sekcím).
- `logic/page-logic.ts` (test vedle): `pageLogic` dělí prvky logiky podle boxů (neznámý box = celá stránka) a počítá starší karty bez `element`.
- `logic/drop-target.ts`: `gridAt`, `sectionAt` (cíl puštění z DOM pod ukazatelem).
- `logic/box-badges.ts` (test vedle): `boxBadges` odvozené značky boxu, nic se neukládá.
- `logic/czech-count.ts` (test vedle).
- `styles/layout-canvas.css`, předpona `layout-canvas` (box `layout-canvas__box--<role>` v barvě role, štítek `layout-canvas__chip`).
