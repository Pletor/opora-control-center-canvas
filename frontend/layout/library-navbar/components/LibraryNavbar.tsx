// Rodič Knihovny: záložky OBSAH | STRÁNKA a pod nimi buď hledání, filtr „Pro tento projekt / Vše“ a jeden
// seznam prvků podle kategorií (`LibraryContent`), nebo strom vrstev (`LibraryPagePanel`). Vlastní
// hlavičku nemá — panel sekce má jednu hlavičku projektu a zavírá se ikonou nebo ☰ (docs/menu-a-katalog.md).
// Rodič nic neukládá: stav dostává v props z `useLibraryNavbar` v App a každou změnu hlásí callbackem.
// Projekt zná jen přes hotový `profile` z App; druh zdroje ani nastavení nečte.
import LibraryContent from "@/layout/library-navbar/components/LibraryContent";
import LibraryPagePanel from "@/layout/library-navbar/components/LibraryPagePanel";
import CatalogScopeBar from "@/layout/panel-dock/components/CatalogScopeBar";
import CatalogOutsideRow from "@/layout/panel-dock/components/CatalogOutsideRow";
import Icon from "@/ui-kit/icon/components/Icon";
import { libraryView } from "@/layout/library-navbar/logic/library-scope";
import type { CatalogScope } from "@/layout/panel-dock/logic/panel-drawer";
import { outsideSummary } from "@/editor/component-library/library-catalog/logic/catalog-fit";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { LIBRARY_TABS, type LibraryNavbarState, type LibraryTab } from "@/layout/library-navbar/logic/library-navbar";
import type { LayerFilter, LayerGroupId } from "@/layout/library-navbar/logic/layer-list";
import { CATALOG_ITEMS, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { IndexMatches } from "@/layout/library-navbar/logic/canvas-index";

/** Stálé prázdné hodnoty, aby výchozí props nedělaly z každého vykreslení nový objekt. */
const EMPTY_CLOSED: ReadonlySet<string> = new Set<string>();
const EMPTY_NODES: CanvasNode[] = [];
const NO_PROFILE: ProjectProfile = { architecture: "", tenancy: "", platform: "web" };

export default function LibraryNavbar({
  state,
  items = CATALOG_ITEMS,
  nodes = EMPTY_NODES,
  closed = EMPTY_CLOSED,
  pageMatches = null,
  profile = NO_PROFILE,
  scope = "fitting",
  showOutside = false,
  onScope,
  onToggleOutside,
  onTab,
  onSearch,
  onItem,
  onPageFilter,
  onPageSearch,
  onToggleGroup,
  onOpenLayer,
}: {
  state: LibraryNavbarState;
  items?: CatalogItem[];
  /** Graf projektu pro záložku STRÁNKA; panel si ho nikdy nenačítá sám. */
  nodes?: CanvasNode[];
  /** Id uzavřených karet (`done.confirmed`) pro značku „skryto“ v seznamu vrstev. */
  closed?: ReadonlySet<string>;
  /** Shody indexu plátna pro hledání ve STRÁNCE; načítá je App, `null` = lokální filtr podle názvu. */
  pageMatches?: IndexMatches | null;
  /** Profil projektu od App; podle něj se katalog zúží. Bez profilu se nic nefiltruje. */
  profile?: ProjectProfile;
  scope?: CatalogScope;
  showOutside?: boolean;
  onScope?: (scope: CatalogScope) => void;
  onToggleOutside?: () => void;
  onTab: (tab: LibraryTab) => void;
  onSearch: (query: string) => void;
  /** Klik na prvek: otevře nebo zavře jeho náhled. */
  onItem: (id: string) => void;
  onPageFilter: (filter: LayerFilter) => void;
  onPageSearch: (query: string) => void;
  onToggleGroup: (group: LayerGroupId) => void;
  /** Klik na vrstvu; co se stane (vstup do vrstvy a výběr karty), rozhoduje rodič. */
  onOpenLayer: (id: string) => void;
}) {
  const view = libraryView(items, profile, { scope, showOutside, query: state.query });
  const found = view.shown;
  // Řádek mimo profil patří k filtru projektu; hledání a „Vše“ už ukazují všechno.
  const outsideRow = view.outside.length > 0 && scope === "fitting" && !state.query.trim();

  return (
    <aside className="library-navbar" aria-label="Knihovna" data-testid="library-navbar">
      <div className="library-navbar__panel">
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
            matches={pageMatches}
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
            <div className="library-navbar__search">
              <Icon className="library-navbar__search-icon" name="search" size={16} />
              <input
                type="search"
                className="library-navbar__search-input"
                placeholder="Najít prvek"
                aria-label="Najít prvek v knihovně"
                value={state.query}
                onChange={(event) => onSearch(event.target.value)}
              />
              <small className="library-navbar__search-count">{found.length}</small>
            </div>
            {view.filtering && onScope && (
              <CatalogScopeBar scope={scope} fitting={view.fittingCount} all={view.allCount} onScope={onScope} />
            )}

            <div className="library-navbar__body">
              <LibraryContent
                categories={view.categories}
                items={found}
                open={state.item}
                notes={view.notes}
                outside={view.outsideIds}
                profileOnly={view.profileOnly}
                onOpen={onItem}
              />
              {outsideRow && onToggleOutside && (
                <CatalogOutsideRow
                  summary={outsideSummary(view.outside, ["prvek", "prvky", "prvků"])}
                  shown={showOutside}
                  onToggle={onToggleOutside}
                />
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
