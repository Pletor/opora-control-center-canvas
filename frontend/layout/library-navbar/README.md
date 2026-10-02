Knihovna: obsah šuplíku Editoru u levého okraje, ze kterého se táhne know-how na plátno. Forma je z kontraktu `docs/panely-editoru.md` (Dílek 2: Knihovna) — rozměry, ikony a barvy kategorií platí pro všechny tři panely editoru stejně; obsah je náš katalog (`frontend/editor/component-library/library-catalog/`), ne položky z inspirace.

Knihovna **není sloupec v toku** a nesbaluje se na lištu. Leží v šuplíku `layout/panel-dock/` (pás 380px u levého okraje, kontrakt `docs/suplik-a-profil.md`) a vyplní jeho tělo pod hlavičkou projektu. Otevírá ji tlačítko, segment v šuplíku nebo zkratka **Ctrl+Shift+,**, zavírá ikona v liště, ☰, Esc nebo přepnutí módu (vlastní hlavičku ani křížek Knihovna nemá); klik na plátno ji nezavře. Kdy je vidět, rozhoduje App a `usePanelDock`; stav Knihovny o viditelnosti nic neví.

**Dílky**

- `components/LibraryNavbar.tsx` — rodič: záložky OBSAH | STRÁNKA a pod nimi buď hledání, filtr projektu a seznam prvků, nebo strom vrstev. Vlastní hlavičku nemá (`docs/menu-a-katalog.md` §A). Nic neukládá; stav dostává v props a změny hlásí callbackem (`onItem`, `onSearch`, `onTab`, …).
- `components/LibraryContent.tsx` — OBSAH: **jeden seznam** prvků podle kategorií, každý prvek právě jednou (přepínač Elementy/Bloky zanikl, §B1). Police = nadpis kategorie s ikonou-žetonem, počtem a případně štítkem „kvůli profilu“; pod ní řádky prvků (`data-testid="library-item-<id>"`) s popiskem, účelem a úchytem. Řádek je zdroj tažení; klik (`aria-expanded`) otevře pod ním náhled.
- `components/LibraryItemDetail.tsx` — náhled otevřeného prvku (`data-testid="library-detail-<id>"`): Souvisí s (`@id` přeložené na název a účel), Hotovo, když, Hranice (musí / nesmí), Kroky a Šablona. Prázdné části se nekreslí.
- `components/LibraryPagePanel.tsx` — záložka STRÁNKA: seznam vrstev nad grafem projektu. Nahoře filtr Vše | Sektory | Uzly | Oblasti a vlastní hledání, pod tím sbalitelné skupiny. Uzly, uzavřené karty i stav filtru dostává v props; klik na řádek hlásí `onOpenLayer(id)` nahoru.
- `components/LibraryEdgeGroup.tsx` — skupina „Vazby“ pod stromem (jen filtr Vše a jen se shodami z indexu): řádek `fromName → toName` a pod ním zkrácené předání; klik hlásí `onOpenLayer(from)`, tedy otevře zdrojovou kartu vazby.
- `components/LibraryLayerGroup.tsx` — jedna skupina seznamu: hlavička (šipka `chevron-right`, u rozbalené skupiny otočená o 90° modifikátorem `--open`, název, počet) a pod ní řádky stromu. Řádek nese značku druhu (žeton 24px s ikonou z `layerKindIcon`), jméno, odsazení podle hloubky (`library-navbar__row--depth-<0..4>`), domeček (`home`) u vrstvy ležící rovnou v projektu a tichou značku „skryto“ u uzavřené karty (ztlumí se celý řádek, ne jen text).

**Seznam vrstev (STRÁNKA)**

`logic/layer-list.ts` je čistá logika s testem vedle. `buildLayerTree(nodes, filter, query, closed)` vezme `graph.nodes` a vrátí skupiny, které filtr propouští:

- **Sektory** — sektor v projektu a pod ním rekurzivně jeho uzly i podsektory, odsazené podle zanoření.
- **Uzly mimo sektor** — uzly ležící rovnou v projektu, i s vlastním obsahem.
- **Oblasti** — popisek přes `areaLabel`, odsazení podle vrstvy, na které oblast stojí; oblasti téže vrstvy drží pohromadě.

**Hledání přes index plátna** (`docs/kontext-karet-a-index.md` §5): s neprázdným dotazem App přes `logic/use-canvas-index.ts` (`useCanvasIndex`, debounce 200 ms, jen při otevřené záložce STRÁNKA) zavolá `GET /api/canvas-index?project=&workspace=&q=&limit=2000` stávajícím helperem `api()`. `logic/canvas-index.ts` (+ test) z odpovědi udělá `IndexMatches` — `ids` karet (vše kromě `kind: "edge"`) a `edges` pro skupinu „Vazby“. `buildLayerTree(nodes, filter, query, closed, matches)` pak ukáže jen shody a jejich předky (obsah shody jen tehdy, když sám odpovídá). Dokud odpověď nedorazí, nebo když endpoint selže či vrátí neznámý tvar, je `matches` `null` a platí původní lokální filtr podle názvu. Bez dotazu se nic nevolá. Panel sám nic nenačítá; shody dostává jako `pageMatches` / `matches` v props.

Komentář není vrstva, do které se dá vejít, a v seznamu se neobjeví. Sirotek (uzel, jehož vrstva už v grafu není) vyjde nahoru bez domečku, aby se neztratil; kruh v datech se usekne, panel se nezacyklí. Hledání zahazuje diakritiku (`foldDiacritics` z katalogu): co dotazu odpovídá, ukáže se i s celým svým obsahem, a jeho předkové zůstanou jako cesta, aby bylo vidět, kde nález leží. Řádek je `{id, name, kind, depth, isRoot, hidden}` — `isRoot` kreslí domeček, `hidden` značku „skryto“ u uzavřené karty.

**Stav**

`logic/library-navbar.ts` drží čistý model (`emptyLibraryNavbar`, `setTab`, `setQuery`, `openItem`, `setPageFilter`, `setPageQuery`, `toggleGroup`, `parseLibraryNavbar`, `categoryIcon`, `layerKindIcon`, `isLibraryCollapseShortcut`) s testem vedle; `logic/use-library-navbar.ts` je jen vazba na React (`useLibraryNavbar()`), kterou volá App a výsledek rozdá dílkům. Posluchač zkratky tu už není — drží ho `layout/panel-dock/`. Celý stav panelu (záložka, hledání v katalogu, otevřený prvek **a** filtr vrstev, hledání vrstev, sbalené skupiny) se ukládá pod **jediným klíčem pro celou aplikaci**: `opora:library-navbar:v1`. Nikdy per projekt, nikdy druhý klíč. Katalog a STRÁNKA mají vlastní pole hledání (`query` × `pageQuery`), takže přepnutí záložky nesmaže rozepsaný dotaz. Panel nečte `sourceKind`, id projektu ani pracovní prostor — chová se ve všech projektech stejně.

Starší preference s `mode` (Elementy/Bloky) a `category` se při čtení zahodí; neznámé id otevřeného prvku taky.

Stav **nenese viditelnost**: `expanded`, `toggleExpanded` a `expandToCategory` se zrušily. Starší preference nesly `open` a `expanded`; obě se při čtení zahodí, takže po načtení stránky je Knihovna vždy zavřená.

`isLibraryCollapseShortcut(event)` je pravidlo zkratky **Ctrl+Shift+,** (na Macu ⌘⇧,; platí „,“ i „<“, ne s Altem) — zrcadlo `isCollapseShortcut` (Ctrl+Shift+.) v `layout/agent-navbar/logic/agent-navbar.ts`. Znovu ho používá `panelForShortcut` v `layout/panel-dock/logic/panel-dock.ts`. Čárka je vlevo od tečky tak, jako je tlačítko Knihovna vlevo od Agentů a postupů.

`categoryIcon(id)` vrací **jméno ikony** ze sady `ui-kit/icon/` podle tabulky v `docs/panely-editoru.md` (doladění bod 4): fe-components → `component`, fe-logic → `function-square`, fe-css → `palette`, backend → `server`, database → `database`, cache → `refresh-cw`, security → `shield`, cloud → `cloud`, tests → `check-circle`; neznámé id dostane `component`. Používá ji `LibraryContent`, takže stejná kategorie nese stejnou ikonu všude v panelu. `layerKindIcon(kind)` dělá totéž pro strom vrstev: sektor → `layout-grid`, uzel → `component`, oblast → `map`, cokoli jiného (komentář, cizí druh) → `component`. Unicode glyfy (▤ ƒ ◐ ⚙ ▦ ⟳ ⛨ ☁ ✓ ⌕ ⋮⋮ ⇤ ⇥ › ‹ ⌂) se ruší; kreslí se SVG se stopou 1.75px.

**Tažení (zdroj)**

`startCatalogDrag(dataTransfer, itemId)` zapíše do schránky tažení jen id položky pod typem `application/x-opora-catalog-item` (konstanta `CATALOG_DRAG_TYPE` v katalogu) a nastaví `effectAllowed = "copy"`. Tím zdroj tažení končí. Co z prvku vznikne, určí místo puštění: na kartu blok, na prázdné plátno nová karta (Board → App → `catalog-insert.ts`). Cíl si položku dohledá přes `itemById(id)`.

**Styl**

`styles/library-navbar.css`, blok `library-navbar`, BEM `blok__prvek--varianta`, každý blok začíná příběhovým komentářem. Knihovna vyplní zavěšený panel (`width` i `height` 100 %, bez vlastního rámečku, rohy `border-radius: inherit` od panelu), bez modifikátoru `--collapsed` a bez media dotazu. Míry jsou podle kontraktu `docs/panely-editoru.md` v px (hledání 36px, řádek min. 40px, ikona-žeton 28px/rádius 8px). Barva kategorie sedí na modifikátoru police, který ji nastaví jako `--c` (`.library-navbar__shelf--backend`); potomci (ikona-žeton, pruh prvku, výplň otevřeného prvku) čtou jen `var(--c)`. Barvy jen z tokenů (`design-tokens/styles/theme-tokens.css`, `--cat-<id>`/`--cat-soft`), takže panel drží světlý i tmavý režim beze změny kódu. Náhled prvku je pod řádkem uvnitř panelu, nic z panelu nevyčnívá; šablona roluje do strany uvnitř náhledu.

**Zapojení**

Knihovnu otevírá ikona v liště menu ☰ (`layout/panel-dock/`, `DockRail`); `app/components/App.tsx` volá `useLibraryNavbar()` jednou a vykresluje `<LibraryNavbar/>` **uvnitř `<PanelDrawer>`**, jen v prostředí Editoru a jen když je otevřený panel `library` (zásuvka `NodeLibraryDrawer` zůstává uvnitř plátna, to jsou dvě různé věci). App panelu podává `nodes={graph.nodes}`, `closed={closedNodeIds}` (id karet s `done.confirmed` ze stavu plochy), `onOpenLayer={openNode}` a `onItem={libraryNavbar.item}` — `onOpenLayer` jde touž cestou, kterou už chodí odkaz i souvislost: vstup do rodičovské vrstvy a výběr karty. Panel o plátně nic neví a sám nic nenačítá.

**Profil projektu (docs/suplik-a-profil.md)**

Knihovna dostává od App hotový `profile` (`catalogProfile` z `shared/project-capabilities`) a stav filtru (`scope`, `showOutside`, `onScope`, `onToggleOutside` z `usePanelDrawer`). Sama nastavení ani `sourceKind` nečte. `logic/library-scope.ts` (+ test) — `libraryView(items, profile, options)`: rozdělí katalog přes `catalogView` šuplíku, kategorie „jen kvůli profilu“ (`profileOnly`) dá nahoru se štítkem „kvůli profilu“ a ke každému prvku dá poznámku (`notes`: „kvůli profilu: …“ / „mimo profil“). Pod hledáním je `CatalogScopeBar` (jen s nastaveným profilem), na konci seznamu `CatalogOutsideRow`. Hledání prohledá i prvky mimo profil; ty jsou ztlumené (`library-navbar__tile--outside`, `library-navbar__preview--outside`). Nová kategorie Multitenance (`tenancy`) má ikonu `users` a barvu `--accent`.
