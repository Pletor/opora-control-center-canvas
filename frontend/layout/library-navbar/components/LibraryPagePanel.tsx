// Záložka STRÁNKA: seznam vrstev nad grafem projektu. Nahoře filtr (Vše / Sektory / Uzly / Oblasti)
// a hledání, pod tím sbalitelné skupiny se stromem. Dílek nic nepočítá sám — uzly, uzavřené karty
// a stav filtru dostává v props, klik na řádek hlásí callbackem nahoru a rodič (App) z něj udělá
// vstup do vrstvy a výběr karty.
import { useMemo } from "react";
import LibraryLayerGroup from "@/layout/library-navbar/components/LibraryLayerGroup";
import {
  buildLayerTree,
  countLayers,
  LAYER_FILTERS,
  LAYER_GROUPS,
  type LayerFilter,
  type LayerGroupId,
} from "@/layout/library-navbar/logic/layer-list";
import type { CanvasNode } from "@/shared/types/logic/types";

export default function LibraryPagePanel({
  nodes,
  closed,
  filter,
  query,
  collapsed,
  onFilter,
  onSearch,
  onToggleGroup,
  onOpenLayer,
}: {
  /** Celý graf projektu, ne jen aktuální vrstva: seznam vrstev ukazuje projekt shora. */
  nodes: CanvasNode[];
  /** Id uzavřených karet (`done.confirmed`); panel je jen kreslí jako skryté. */
  closed: ReadonlySet<string>;
  filter: LayerFilter;
  query: string;
  collapsed: LayerGroupId[];
  onFilter: (filter: LayerFilter) => void;
  onSearch: (query: string) => void;
  onToggleGroup: (group: LayerGroupId) => void;
  onOpenLayer: (id: string) => void;
}) {
  const groups = useMemo(() => buildLayerTree(nodes, filter, query, closed), [nodes, filter, query, closed]);
  // Prázdná skupina má říct pravdivý důvod: při hledání je vinen dotaz, jinak je tam opravdu prázdno.
  const emptyOf = (id: LayerGroupId) =>
    query.trim() ? "Hledání tu nic nenašlo." : LAYER_GROUPS.find((group) => group.id === id)?.empty ?? "";
  return (
    <div className="library-navbar__page">
      <div className="library-navbar__filters" role="group" aria-label="Které vrstvy ukázat">
        {LAYER_FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={"library-navbar__filter" + (filter === item.id ? " library-navbar__filter--active" : "")}
            aria-pressed={filter === item.id}
            data-testid={"library-filter-" + item.id}
            onClick={() => onFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="library-navbar__search">
        <input
          type="search"
          className="library-navbar__search-input"
          placeholder="Najít vrstvu"
          aria-label="Najít vrstvu v projektu"
          value={query}
          onChange={(event) => onSearch(event.target.value)}
        />
        <small className="library-navbar__search-count">{countLayers(groups)}</small>
      </div>

      <div className="library-navbar__page-list">
        {groups.map((group) => (
          <LibraryLayerGroup
            key={group.id}
            group={group}
            empty={emptyOf(group.id)}
            collapsed={collapsed.includes(group.id)}
            onToggle={() => onToggleGroup(group.id)}
            onOpen={onOpenLayer}
          />
        ))}
      </div>
    </div>
  );
}
