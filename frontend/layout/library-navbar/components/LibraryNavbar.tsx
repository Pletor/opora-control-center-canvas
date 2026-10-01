// Rodič Knihovny: hlavička s vrstvou a křížkem, záložky OBSAH | STRÁNKA, přepínač Elementy | Bloky,
// hledání a pod ním jeden ze tří dílků. Rodič nic neukládá sám — stav dostává v props z `useLibraryNavbar`
// v App a každou změnu hlásí callbackem nahoru. O projektu ani o druhu zdroje neví nic; panel je jeden
// pro celou aplikaci.
//
// Knihovna visí v zavěšeném panelu (`layout/panel-dock/`) a vyplní ho celý. Kdy je vidět, rozhoduje
// App; dílek se jen nakreslí a křížek v hlavičce ohlásí `onClose` nahoru.
import LibraryTiles from "@/layout/library-navbar/components/LibraryTiles";
import LibraryCategories from "@/layout/library-navbar/components/LibraryCategories";
import LibraryPagePanel from "@/layout/library-navbar/components/LibraryPagePanel";
import Icon from "@/ui-kit/icon/components/Icon";
import {
  LIBRARY_MODES,
  LIBRARY_TABS,
  type LibraryMode,
  type LibraryNavbarState,
  type LibraryTab,
} from "@/layout/library-navbar/logic/library-navbar";
import type { LayerFilter, LayerGroupId } from "@/layout/library-navbar/logic/layer-list";
import {
  CATALOG_CATEGORIES,
  CATALOG_ITEMS,
  searchItems,
  type CatalogCategory,
  type CatalogItem,
} from "@/editor/component-library/library-catalog/logic/library-catalog";
import type { CanvasNode } from "@/shared/types/logic/types";

/** Stálé prázdné hodnoty, aby výchozí props nedělaly z každého vykreslení nový objekt. */
const EMPTY_CLOSED: ReadonlySet<string> = new Set<string>();
const EMPTY_NODES: CanvasNode[] = [];

export default function LibraryNavbar({
  state,
  layerName,
  items = CATALOG_ITEMS,
  nodes = EMPTY_NODES,
  closed = EMPTY_CLOSED,
  onTab,
  onMode,
  onSearch,
  onCategory,
  onPageFilter,
  onPageSearch,
  onToggleGroup,
  onOpenLayer,
  onBack,
  onClose,
}: {
  state: LibraryNavbarState;
  /** Jméno vrstvy, ve které uživatel stojí; panel ho jen ukazuje. */
  layerName: string;
  items?: CatalogItem[];
  /** Graf projektu pro záložku STRÁNKA; panel si ho nikdy nenačítá sám. */
  nodes?: CanvasNode[];
  /** Id uzavřených karet (`done.confirmed`) pro značku „skryto“ v seznamu vrstev. */
  closed?: ReadonlySet<string>;
  onTab: (tab: LibraryTab) => void;
  onMode: (mode: LibraryMode) => void;
  onSearch: (query: string) => void;
  onCategory: (category: CatalogCategory) => void;
  onPageFilter: (filter: LayerFilter) => void;
  onPageSearch: (query: string) => void;
  onToggleGroup: (group: LayerGroupId) => void;
  /** Klik na vrstvu; co se stane (vstup do vrstvy a výběr karty), rozhoduje rodič. */
  onOpenLayer: (id: string) => void;
  /** Šipka zpět o vrstvu výš; bez ní je šipka zhasnutá (jsme na kořeni). */
  onBack?: () => void;
  /** Křížek v hlavičce: zavře zavěšený panel; co to znamená, rozhoduje rodič. */
  onClose: () => void;
}) {
  const found = searchItems(items, state.query);
  const categories = CATALOG_CATEGORIES.filter((category) => found.some((item) => item.category === category.id));

  return (
    <aside className="library-navbar" aria-label="Knihovna" data-testid="library-navbar">
      <div className="library-navbar__panel">
        <header className="library-navbar__head">
          <button
            type="button"
            className="library-navbar__back"
            aria-label="Zpět o vrstvu výš"
            disabled={!onBack}
            onClick={onBack}
          >
            <Icon name="chevron-left" size={16} />
          </button>
          <strong className="library-navbar__layer">{layerName}</strong>
          <button
            type="button"
            className="library-navbar__close"
            aria-label="Zavřít Knihovnu"
            title="Zavřít Knihovnu (Esc)"
            data-testid="library-close"
            onClick={onClose}
          >
            <Icon name="x" size={16} />
          </button>
        </header>

        <nav className="library-navbar__tabs" role="tablist" aria-label="Záložky knihovny">
          {LIBRARY_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className={"library-navbar__tab" + (state.tab === tab.id ? " library-navbar__tab--active" : "")}
              aria-selected={state.tab === tab.id}
              data-testid={"library-tab-" + tab.id}
              onClick={() => onTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {state.tab === "page" ? (
          <LibraryPagePanel
            nodes={nodes}
            closed={closed}
            filter={state.pageFilter}
            query={state.pageQuery}
            collapsed={state.collapsed}
            onFilter={onPageFilter}
            onSearch={onPageSearch}
            onToggleGroup={onToggleGroup}
            onOpenLayer={onOpenLayer}
          />
        ) : (
          <>
            <div className="library-navbar__switch" role="group" aria-label="Pohled na katalog">
              {LIBRARY_MODES.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  className={"library-navbar__switch-button" + (state.mode === mode.id ? " library-navbar__switch-button--active" : "")}
                  aria-pressed={state.mode === mode.id}
                  title={mode.hint}
                  data-testid={"library-mode-" + mode.id}
                  onClick={() => onMode(mode.id)}
                >
                  {mode.label}
                </button>
              ))}
            </div>

            <div className="library-navbar__search">
              <Icon className="library-navbar__search-icon" name="search" size={16} />
              <input
                type="search"
                className="library-navbar__search-input"
                placeholder="Najít položku"
                aria-label="Najít položku v knihovně"
                value={state.query}
                onChange={(event) => onSearch(event.target.value)}
              />
              <small className="library-navbar__search-count">{found.length}</small>
            </div>

            <div className="library-navbar__body">
              {state.mode === "elements" ? (
                <LibraryTiles items={found} onOpenCategory={onCategory} />
              ) : (
                <LibraryCategories categories={categories} items={found} open={state.category} onOpen={onCategory} />
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
