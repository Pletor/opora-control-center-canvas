// Stav sekce Struktura bez Reactu: který filtr vrstev, co se hledá a které skupiny jsou sbalené.
// Jestli je Struktura vidět, tu není — to drží menu (`layout/panel-dock/`). Stav je jeden pro celou
// aplikaci (neví nic o projektu ani o druhu zdroje), proto se ukládá pod jediným klíčem
// `opora:structure-panel:v1`. Dřív tyto tři hodnoty žily v záložce Struktura Knihovny pod klíčem
// `opora:library-navbar:v1`; při prvním čtení se odtud převezmou a starý klíč se při zápisu smaže.
import { LAYER_FILTERS, LAYER_GROUPS, type LayerFilter, type LayerGroupId } from "@/layout/structure-panel/logic/layer-list";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

/** Záložky sekce: strom vrstev, nebo co dostane agent vybrané karty. */
export type StructureTab = "tree" | "card";
export const STRUCTURE_TABS: { id: StructureTab; label: string }[] = [
  { id: "tree", label: "Struktura" },
  { id: "card", label: "Vybraná karta" },
];

export type StructureState = {
  /** Viditelná záložka; výběr karty na plátně ji sám nepřepíná. */
  tab: StructureTab;
  /** Která skupina vrstev se ukazuje; `all` je výchozí. */
  filter: LayerFilter;
  query: string;
  /** Skupiny, které si uživatel sbalil. Co v seznamu není, je rozbalené. */
  collapsed: LayerGroupId[];
};

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const STRUCTURE_PANEL_KEY = "opora:structure-panel:v1";
/** Klíč zrušené Knihovny: jen ke převzetí uložených hodnot Struktury. */
export const LEGACY_LIBRARY_KEY = "opora:library-navbar:v1";

export const emptyStructure = (): StructureState => ({ tab: "tree", filter: "all", query: "", collapsed: [] });

export const setTab = (state: StructureState, tab: StructureTab): StructureState => ({ ...state, tab });
export const setFilter = (state: StructureState, filter: LayerFilter): StructureState => ({ ...state, filter });
export const setQuery = (state: StructureState, query: string): StructureState => ({ ...state, query });
/** Klik na hlavičku skupinu sbalí, druhý ji rozbalí. */
export const toggleGroup = (state: StructureState, group: LayerGroupId): StructureState => ({
  ...state,
  collapsed: state.collapsed.includes(group) ? state.collapsed.filter((id) => id !== group) : [...state.collapsed, group],
});

const KNOWN_FILTERS = new Set<string>(LAYER_FILTERS.map((filter) => filter.id));
const KNOWN_GROUPS = new Set<string>(LAYER_GROUPS.map((group) => group.id));

function fromValues(filter: unknown, query: unknown, collapsed: unknown, tab: unknown = "tree"): StructureState {
  return {
    tab: tab === "card" ? "card" : "tree",
    filter: typeof filter === "string" && KNOWN_FILTERS.has(filter) ? (filter as LayerFilter) : "all",
    query: typeof query === "string" ? query.slice(0, 120) : "",
    collapsed: Array.isArray(collapsed)
      ? (collapsed.filter((id) => typeof id === "string" && KNOWN_GROUPS.has(id)) as LayerGroupId[])
      : [],
  };
}

/**
 * Uložená preference je cizí text: co nesedí, se tiše nahradí výchozím stavem. Bez vlastního klíče
 * se převezme `pageFilter`, `pageQuery` a `collapsed` ze staré Knihovny.
 */
export function parseStructure(raw: string | null, legacy: string | null = null): StructureState {
  try {
    const value = raw ? (JSON.parse(raw) as Record<string, unknown> | null) : null;
    if (value && typeof value === "object") return fromValues(value.filter, value.query, value.collapsed, value.tab);
    const old = legacy ? (JSON.parse(legacy) as Record<string, unknown> | null) : null;
    if (old && typeof old === "object") return fromValues(old.pageFilter, old.pageQuery, old.collapsed);
  } catch {
    /* rozbitý JSON = výchozí stav */
  }
  return emptyStructure();
}

export function readStructure(): StructureState {
  try {
    return parseStructure(localStorage.getItem(STRUCTURE_PANEL_KEY), localStorage.getItem(LEGACY_LIBRARY_KEY));
  } catch {
    return emptyStructure();
  }
}

/** Zápis preference nikdy neshodí panel; osiřelý klíč staré Knihovny se přitom uklidí. */
export function writeStructure(state: StructureState): boolean {
  try {
    localStorage.setItem(STRUCTURE_PANEL_KEY, JSON.stringify(state));
    localStorage.removeItem(LEGACY_LIBRARY_KEY);
    return true;
  } catch {
    return false;
  }
}

/** Značka druhu vrstvy ve stromu: sektor je rozdělená plocha, uzel dílek, oblast mapa.
    Komentář ani cizí druh vrstva nejsou — dostanou ikonu uzlu, aby řádek nezůstal prázdný. */
const LAYER_KIND_ICON: Record<string, IconName> = { sector: "layout-grid", node: "component", area: "map" };

export function layerKindIcon(kind: string): IconName {
  return LAYER_KIND_ICON[kind] ?? "component";
}
