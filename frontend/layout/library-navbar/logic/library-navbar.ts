// Stav Knihovny bez Reactu: která záložka, co se hledá a který prvek má otevřený náhled.
// Jestli je Knihovna vidět, tu není — to drží šuplík (`layout/panel-dock/`) jen v paměti
// sezení. Stav je jeden pro celou aplikaci — neví nic o projektu, pracovním prostoru ani o druhu
// zdroje, a proto se ukládá pod jediným klíčem `opora:library-navbar:v1`.
import { CATALOG_DRAG_TYPE, itemById, type CatalogCategory } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { LAYER_FILTERS, LAYER_GROUPS, type LayerFilter, type LayerGroupId } from "@/layout/library-navbar/logic/layer-list";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

/** Záložky v hlavě panelu: obsah knihovny × stránka (seznam vrstev nad grafem). */
export type LibraryTab = "content" | "page";

export type LibraryNavbarState = {
  tab: LibraryTab;
  query: string;
  /** Prvek s otevřeným náhledem (účel, souvislosti, hotovo, invarianty, šablona); `null` = žádný. */
  item: string | null;
  /** STRÁNKA: která skupina vrstev se ukazuje. Vlastní pole, aby filtr katalogu zůstal nedotčený. */
  pageFilter: LayerFilter;
  /** STRÁNKA: vlastní hledání, aby se přepnutím záložky neztratil rozepsaný dotaz v katalogu. */
  pageQuery: string;
  /** STRÁNKA: skupiny, které si uživatel sbalil. Co v seznamu není, je rozbalené. */
  collapsed: LayerGroupId[];
};

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const LIBRARY_NAVBAR_KEY = "opora:library-navbar:v1";

/**
 * Ikona kategorie bloků podle tabulky v `docs/panely-editoru.md` (doladění bod 4). Vrací se jméno
 * ze sady `ui-kit/icon`, ne Unicode znak: glyfy (▤ ƒ ◐ ⚙) se v každém systému kreslí jinak a leckde
 * chybí. Mapování je věc panelu — katalog dál nese jen id, název a nápovědu kategorie.
 */
const CATEGORY_ICON: Record<CatalogCategory, IconName> = {
  "fe-components": "component",
  "fe-logic": "function-square",
  "fe-css": "palette",
  backend: "server",
  database: "database",
  cache: "refresh-cw",
  security: "shield",
  cloud: "cloud",
  tests: "check-circle",
  tenancy: "users",
};

/** Neznámá nebo cizí kategorie dostane dílek — lišta i dlaždice tak nikdy nezůstanou bez ikony. */
export function categoryIcon(id: string): IconName {
  return (CATEGORY_ICON as Record<string, IconName>)[id] ?? "component";
}

/** Značka druhu vrstvy ve stromu STRÁNKY: sektor je rozdělená plocha, uzel dílek, oblast mapa.
    Komentář ani cizí druh vrstva nejsou — dostanou ikonu uzlu, aby řádek nezůstal prázdný. */
const LAYER_KIND_ICON: Record<string, IconName> = {
  sector: "layout-grid",
  node: "component",
  area: "map",
};

export function layerKindIcon(kind: string): IconName {
  return LAYER_KIND_ICON[kind] ?? "component";
}

export const LIBRARY_TABS: { id: LibraryTab; label: string }[] = [
  { id: "content", label: "Prvky" },
  { id: "page", label: "Struktura" },
];

export const emptyLibraryNavbar = (): LibraryNavbarState => ({
  tab: "content",
  query: "",
  item: null,
  pageFilter: "all",
  pageQuery: "",
  collapsed: [],
});

/** Záložka mění jen sebe: hledání i otevřený náhled čekají, až se uživatel vrátí na OBSAH. */
export const setTab = (state: LibraryNavbarState, tab: LibraryTab): LibraryNavbarState => ({ ...state, tab });
export const setQuery = (state: LibraryNavbarState, query: string): LibraryNavbarState => ({ ...state, query });
/** Klik na prvek otevře jeho náhled, klik na tentýž ho zavře; otevřený je vždy nejvýš jeden. */
export const openItem = (state: LibraryNavbarState, item: string): LibraryNavbarState => ({
  ...state,
  item: state.item === item ? null : item,
});

/** Filtr STRÁNKY; `all` je výchozí, takže seznam napoprvé ukáže všechny tři skupiny. */
export const setPageFilter = (state: LibraryNavbarState, pageFilter: LayerFilter): LibraryNavbarState => ({ ...state, pageFilter });
export const setPageQuery = (state: LibraryNavbarState, pageQuery: string): LibraryNavbarState => ({ ...state, pageQuery });
/** Klik na hlavičku skupinu sbalí, druhý ji rozbalí; drží se to v tomtéž klíči jako zbytek panelu. */
export const toggleGroup = (state: LibraryNavbarState, group: LayerGroupId): LibraryNavbarState => ({
  ...state,
  collapsed: state.collapsed.includes(group) ? state.collapsed.filter((id) => id !== group) : [...state.collapsed, group],
});

const KNOWN_FILTERS = new Set<string>(LAYER_FILTERS.map((filter) => filter.id));
const KNOWN_GROUPS = new Set<string>(LAYER_GROUPS.map((group) => group.id));

/** Uložená preference je cizí text: co nesedí, se tiše nahradí výchozím stavem. */
export function parseLibraryNavbar(raw: string | null): LibraryNavbarState {
  const empty = emptyLibraryNavbar();
  if (!raw) return empty;
  try {
    const value = JSON.parse(raw) as Partial<LibraryNavbarState> | null;
    if (!value || typeof value !== "object") return empty;
    return {
      // Starší preference nesly `open`, `expanded`, `mode` (Elementy/Bloky) a `category`. Nic z toho
      // dnes neplatí, proto se to při čtení zahodí; Knihovna je po načtení stránky vždy zavřená.
      tab: value.tab === "page" ? "page" : "content",
      query: typeof value.query === "string" ? value.query.slice(0, 120) : "",
      item: typeof value.item === "string" && itemById(value.item) ? value.item : null,
      pageFilter: typeof value.pageFilter === "string" && KNOWN_FILTERS.has(value.pageFilter) ? (value.pageFilter as LayerFilter) : empty.pageFilter,
      pageQuery: typeof value.pageQuery === "string" ? value.pageQuery.slice(0, 120) : "",
      collapsed: Array.isArray(value.collapsed)
        ? (value.collapsed.filter((id) => typeof id === "string" && KNOWN_GROUPS.has(id)) as LayerGroupId[])
        : [],
    };
  } catch {
    return empty;
  }
}

/** Čtení preference; prohlížeč bez úložiště (soukromé okno, test) dostane výchozí stav. */
export function readLibraryNavbar(): LibraryNavbarState {
  try {
    return parseLibraryNavbar(localStorage.getItem(LIBRARY_NAVBAR_KEY));
  } catch {
    return emptyLibraryNavbar();
  }
}

/** Zápis preference nikdy neshodí panel: když úložiště není, jen se nic neuloží. */
export function writeLibraryNavbar(state: LibraryNavbarState): boolean {
  try {
    localStorage.setItem(LIBRARY_NAVBAR_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/** Jen ta část události, na které pravidlo stojí — díky tomu jde přečíst i z prostého objektu v testu. */
export type ShortcutKey = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">;

/**
 * Ctrl+Shift+, (na Macu ⌘⇧,) otevře a zavře Knihovnu; posluchač drží `layout/panel-dock/`. Je to
 * zrcadlo zkratky Agentů a postupů (Ctrl+Shift+. v `layout/agent-navbar/logic/agent-navbar.ts`):
 * čárka je na klávesnici vlevo od tečky tak, jako je tlačítko Knihovna vlevo od Agentů a postupů. Podle rozložení klávesnice přijde z téhle
 * kombinace „,“ nebo „<“, proto platí obojí. Alt drží stranou jiné zkratky plochy a samotná čárka
 * bez modifikátorů patří psaní.
 */
export function isLibraryCollapseShortcut(event: ShortcutKey): boolean {
  if (event.altKey) return false;
  if (!event.ctrlKey && !event.metaKey) return false;
  if (!event.shiftKey) return false;
  return event.key === "," || event.key === "<";
}

/**
 * Zdroj tažení: do schránky tažení jde jen id položky pod typem `application/x-opora-catalog-item`.
 * Cíl (plátno, fáze 3) si položku dohledá přes `itemById`; panel o plátně nic neví.
 */
export function startCatalogDrag(transfer: DataTransfer, itemId: string): void {
  transfer.setData(CATALOG_DRAG_TYPE, itemId);
  transfer.effectAllowed = "copy";
}
