Sekce **Struktura** menu Editoru (`layout/panel-dock/`, zkratka Ctrl+Shift+,) se dvěma záložkami **Struktura | Vybraná karta**: strom vrstev projektu, nebo co dostane agent vybrané karty — vždy jen jedno, s vlastním posunem, nic se nepřekrývá. Vznikla z bývalé záložky Struktura sekce Knihovna (smazaná `layout/library-navbar/`) a záložky Vybraná karta sekce Agenti (smazaná `layout/agent-navbar/`).

**Dílky**

- `components/StructurePanel.tsx` — rodič sekce (`data-testid="structure-panel"`): přepínač záložek (`role="tablist"`, `data-testid="structure-tab-<tree|card>"`) a jedna plocha. Záložka Struktura = `StructureTree` + akce kostry (`actions`, dílek `editor/skeleton/SkeletonActions`); záložka Vybraná karta = `selectedCard` (dílek `layout/card-brief/CardBrief`). Výběr karty na plátně záložku nepřepíná. Nic neukládá: stav dostává v props z `useStructurePanel` v App a změny hlásí `onTab`, `onFilter`, `onSearch`, `onToggleGroup`, `onOpenLayer`.
- `components/StructureTree.tsx` — filtr Vše / Sektory / Uzly / Oblasti (`data-testid="structure-filter-<id>"`), hledání vrstvy s počtem a sbalitelné skupiny.
- `components/StructureLayerGroup.tsx` — jedna skupina (Sektory / Uzly mimo sektor / Oblasti), řádky stromu s odsazením přes `--depth-N` (`structure-group-<id>`, `structure-layer-<id>`).
- `components/StructureEdgeGroup.tsx` — skupina „Vazby“ se shodami hledání ve zprávách na vazbách (index plátna).

**Logika** (testy vedle, `npm test`)

- `logic/structure-panel.ts` — stav `{ tab, filter, query, collapsed }` (`STRUCTURE_TABS`), `setTab`, `setFilter`, `setQuery`, `toggleGroup`, `layerKindIcon`. Ukládá se jednou pro aplikaci pod `opora:structure-panel:v1`; bez něj se převezmou `pageFilter`, `pageQuery` a `collapsed` ze starého klíče Knihovny `opora:library-navbar:v1`, který se při zápisu smaže (zbytek starého stavu — záložka, hledání a náhled prvku — osiřel).
- `logic/use-structure-panel.ts` — vazba na React (`useStructurePanel()` → `{ state, tab, filter, search, group }`).
- `logic/layer-list.ts` — strom vrstev z plochého grafu (`buildLayerTree`, `countLayers`, `LAYER_FILTERS`, `LAYER_GROUPS`).
- `logic/canvas-index.ts` + `logic/use-canvas-index.ts` — hledání přes `GET /api/canvas-index` (jen s otevřenou sekcí a neprázdným dotazem); bez odpovědi strom filtruje lokálně podle názvu.

**Styl**

`styles/structure-panel.css`, blok `structure-panel`, BEM s příběhovými komentáři, barvy jen z tokenů.
