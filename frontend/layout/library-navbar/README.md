Knihovna: zavěšený panel Editoru, ze kterého se táhne know-how na plátno. Forma je z kontraktu `docs/panely-editoru.md` (Dílek 2: Knihovna) — rozměry, ikony a barvy kategorií platí pro všechny tři panely editoru stejně; obsah je náš katalog (`frontend/editor/component-library/library-catalog/`), ne položky z inspirace.

Knihovna **není sloupec v toku** a nesbaluje se na lištu. Visí v zavěšeném panelu `layout/panel-dock/` (karta 360px pod tlačítkem „Knihovna“ v liště nástrojů, kontrakt `docs/rozvrzeni-editoru.md`, Dílek 3) a vyplní ho celý na šířku i na výšku. Otevírá ji tlačítko nebo zkratka **Ctrl+Shift+,**, zavírá křížek v hlavičce (`onClose`), Esc, klik mimo panel nebo přepnutí módu. Kdy je vidět, rozhoduje App a `usePanelDock`; stav Knihovny o viditelnosti nic neví.

**Dílky**

- `components/LibraryNavbar.tsx` — rodič: hlavička (šipka o vrstvu výš, jméno vrstvy a vpravo křížek `x`, `aria-label="Zavřít Knihovnu"`, `data-testid="library-close"`, hlásí `onClose`), záložky, přepínač, hledání a jeden ze tří dílků pod tím. Nic neukládá; stav dostává v props a změny hlásí callbackem.
- `components/LibraryTiles.tsx` — Elementy: dvousloupcová mřížka dlaždic. Dlaždice = ikona-žeton kategorie, úchyt `grip-vertical`, popis a dvě značky rozpadu („3 dílky“ v barvě kategorie, „5 pravidel“ neutrálně). Klik otevře rozpad té položky v její kategorii, takže ke stejnému obsahu vede i klávesnice.
- `components/LibraryCategories.tsx` — Bloky: devět kategorií s ikonou-žetonem, šipkou (`chevron-right`, u otevřené `chevron-left`) a počtem; rozbalená kategorie otevře vedle panelu sloupec náhledů s prvními kroky rozpadu.
- `components/LibraryPagePanel.tsx` — záložka STRÁNKA: seznam vrstev nad grafem projektu. Nahoře filtr Vše | Sektory | Uzly | Oblasti a vlastní hledání, pod tím sbalitelné skupiny. Uzly, uzavřené karty i stav filtru dostává v props; klik na řádek hlásí `onOpenLayer(id)` nahoru.
- `components/LibraryLayerGroup.tsx` — jedna skupina seznamu: hlavička (šipka `chevron-right`, u rozbalené skupiny otočená o 90° modifikátorem `--open`, název, počet) a pod ní řádky stromu. Řádek nese značku druhu (žeton 24px s ikonou z `layerKindIcon`), jméno, odsazení podle hloubky (`library-navbar__row--depth-<0..4>`), domeček (`home`) u vrstvy ležící rovnou v projektu a tichou značku „skryto“ u uzavřené karty (ztlumí se celý řádek, ne jen text).

**Seznam vrstev (STRÁNKA)**

`logic/layer-list.ts` je čistá logika s testem vedle. `buildLayerTree(nodes, filter, query, closed)` vezme `graph.nodes` a vrátí skupiny, které filtr propouští:

- **Sektory** — sektor v projektu a pod ním rekurzivně jeho uzly i podsektory, odsazené podle zanoření.
- **Uzly mimo sektor** — uzly ležící rovnou v projektu, i s vlastním obsahem.
- **Oblasti** — popisek přes `areaLabel`, odsazení podle vrstvy, na které oblast stojí; oblasti téže vrstvy drží pohromadě.

Komentář není vrstva, do které se dá vejít, a v seznamu se neobjeví. Sirotek (uzel, jehož vrstva už v grafu není) vyjde nahoru bez domečku, aby se neztratil; kruh v datech se usekne, panel se nezacyklí. Hledání zahazuje diakritiku (`foldDiacritics` z katalogu): co dotazu odpovídá, ukáže se i s celým svým obsahem, a jeho předkové zůstanou jako cesta, aby bylo vidět, kde nález leží. Řádek je `{id, name, kind, depth, isRoot, hidden}` — `isRoot` kreslí domeček, `hidden` značku „skryto“ u uzavřené karty.

**Stav**

`logic/library-navbar.ts` drží čistý model (`emptyLibraryNavbar`, `setTab`, `setMode`, `setQuery`, `openCategory`, `setPageFilter`, `setPageQuery`, `toggleGroup`, `parseLibraryNavbar`, `categoryIcon`, `layerKindIcon`, `isLibraryCollapseShortcut`) s testem vedle; `logic/use-library-navbar.ts` je jen vazba na React (`useLibraryNavbar()`), kterou volá App a výsledek rozdá dílkům. Posluchač zkratky tu už není — drží ho `layout/panel-dock/`. Celý stav panelu (záložka, režim, hledání v katalogu, rozbalená kategorie **a** filtr vrstev, hledání vrstev, sbalené skupiny) se ukládá pod **jediným klíčem pro celou aplikaci**: `opora:library-navbar:v1`. Nikdy per projekt, nikdy druhý klíč. Katalog a STRÁNKA mají vlastní pole hledání (`query` × `pageQuery`), takže přepnutí záložky nesmaže rozepsaný dotaz. Panel nečte `sourceKind`, id projektu ani pracovní prostor — chová se ve všech projektech stejně.

Stav **nenese viditelnost**: `expanded`, `toggleExpanded` a `expandToCategory` se zrušily. Starší preference nesly `open` a `expanded`; obě se při čtení zahodí, takže po načtení stránky je Knihovna vždy zavřená.

`isLibraryCollapseShortcut(event)` je pravidlo zkratky **Ctrl+Shift+,** (na Macu ⌘⇧,; platí „,“ i „<“, ne s Altem) — zrcadlo `isCollapseShortcut` (Ctrl+Shift+.) v `layout/agent-navbar/logic/agent-navbar.ts`. Znovu ho používá `panelForShortcut` v `layout/panel-dock/logic/panel-dock.ts`. Čárka je vlevo od tečky tak, jako je tlačítko Knihovna vlevo od Agentů a postupů.

`categoryIcon(id)` vrací **jméno ikony** ze sady `ui-kit/icon/` podle tabulky v `docs/panely-editoru.md` (doladění bod 4): fe-components → `component`, fe-logic → `function-square`, fe-css → `palette`, backend → `server`, database → `database`, cache → `refresh-cw`, security → `shield`, cloud → `cloud`, tests → `check-circle`; neznámé id dostane `component`. Používají ji `LibraryCategories`/`LibraryTiles`, takže stejná kategorie nese stejnou ikonu všude v panelu. `layerKindIcon(kind)` dělá totéž pro strom vrstev: sektor → `layout-grid`, uzel → `component`, oblast → `map`, cokoli jiného (komentář, cizí druh) → `component`. Unicode glyfy (▤ ƒ ◐ ⚙ ▦ ⟳ ⛨ ☁ ✓ ⌕ ⋮⋮ ⇤ ⇥ › ‹ ⌂) se ruší; kreslí se SVG se stopou 1.75px.

**Tažení (zdroj)**

`startCatalogDrag(dataTransfer, itemId)` zapíše do schránky tažení jen id položky pod typem `application/x-opora-catalog-item` (konstanta `CATALOG_DRAG_TYPE` v katalogu) a nastaví `effectAllowed = "copy"`. Tím zdroj tažení končí: puštění na plátno (karta + bloky rozpadu) je fáze 3 a bydlí u plátna, ne tady. Cíl si položku dohledá přes `itemById(id)`.

**Styl**

`styles/library-navbar.css`, blok `library-navbar`, BEM `blok__prvek--varianta`, každý blok začíná příběhovým komentářem. Knihovna vyplní zavěšený panel (`width` i `height` 100 %, bez vlastního rámečku, rohy `border-radius: inherit` od panelu), bez modifikátoru `--collapsed` a bez media dotazu. Míry jsou podle kontraktu `docs/panely-editoru.md` v px (hlavička 48px, hledání 36px, řádek min. 40px, ikona-žeton 28px/rádius 8px). Barva kategorie vždy sedí na modifikátoru, který ji nastaví jako `--c` (`.library-navbar__category--backend`, `.library-navbar__tile--backend`); potomci (ikona-žeton, pruh, výplň) čtou jen `var(--c)`. Barvy jen z tokenů (`design-tokens/styles/theme-tokens.css`, `--cat-<id>`/`--cat-soft`), takže panel drží světlý i tmavý režim beze změny kódu. Panel je `position: relative` jen kvůli jediné věci, která z něj vyčnívá — sloupci náhledů (`__previews`, `left: 100%`, `z-index: 7`), který vyjíždí vpravo ven ze zavěšeného panelu nad plátno.

**Zapojení**

Tlačítko „Knihovna“ je v `layout/panel-dock/components/PanelToggles.tsx`; `app/components/App.tsx` volá `useLibraryNavbar()` jednou a vykresluje `<LibraryNavbar/>` **uvnitř `<PanelDropdown>`**, jen v prostředí Editoru a jen když je otevřený panel `library` (zásuvka `NodeLibraryDrawer` zůstává uvnitř plátna, to jsou dvě různé věci). App panelu podává `nodes={graph.nodes}`, `closed={closedNodeIds}` (id karet s `done.confirmed` ze stavu plochy), `onOpenLayer={openNode}` a `onClose={dock.close}` — `onOpenLayer` jde touž cestou, kterou už chodí odkaz i souvislost: vstup do rodičovské vrstvy a výběr karty. Panel o plátně nic neví a sám nic nenačítá.
