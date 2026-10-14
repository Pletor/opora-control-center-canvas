// Strom Struktury: seznam vrstev nad grafem projektu. Nahoře filtr (Vše / Sektory / Uzly / Oblasti)
// a hledání, pod tím sbalitelné skupiny se stromem. Dílek nic nepočítá sám — uzly, uzavřené karty
// a stav filtru dostává v props, klik na řádek hlásí callbackem nahoru a rodič (App) z něj udělá
// vstup do vrstvy a výběr karty.
import { useMemo } from "react";
import StructureLayerGroup from "@/layout/structure-panel/components/StructureLayerGroup";
import StructureEdgeGroup from "@/layout/structure-panel/components/StructureEdgeGroup";
import type { IndexMatches } from "@/layout/structure-panel/logic/canvas-index";
import {
  buildLayerTree,
  countLayers,
  LAYER_FILTERS,
  LAYER_GROUPS,
  type LayerFilter,
  type LayerGroupId,
} from "@/layout/structure-panel/logic/layer-list";
import type { CanvasNode } from "@/shared/types/logic/types";

export default function StructureTree({
  nodes,
  closed,
  matches = null,
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
  /**
   * Shody indexu plátna pro aktuální dotaz (App je načte přes `useCanvasIndex`). `null` = index
   * nedorazil nebo selhal; strom pak filtruje lokálně podle názvu jako dřív.
   */
  matches?: IndexMatches | null;
  filter: LayerFilter;
  query: string;
  collapsed: LayerGroupId[];
  onFilter: (filter: LayerFilter) => void;
  onSearch: (query: string) => void;
  onToggleGroup: (group: LayerGroupId) => void;
  onOpenLayer: (id: string) => void;
}) {
  const groups = useMemo(() => buildLayerTree(nodes, filter, query, closed, matches?.ids ?? null), [nodes, filter, query, closed, matches]);
  // Vazby nejsou vrstva: ukážou se jen pod „Vše“ a jen se shodami z indexu.
  const edges = filter === "all" && query.trim() ? matches?.edges ?? [] : [];
  // Prázdná skupina má říct pravdivý důvod: při hledání je vinen dotaz, jinak je tam opravdu prázdno.
  const emptyOf = (id: LayerGroupId) =>
    query.trim() ? "Hledání tu nic nenašlo." : LAYER_GROUPS.find((group) => group.id === id)?.empty ?? "";
  return (
    <div className="structure-panel__page">
      <div className="structure-panel__filters" role="group" aria-label="Které vrstvy ukázat">
        {LAYER_FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={"structure-panel__filter" + (filter === item.id ? " structure-panel__filter--active" : "")}
            aria-pressed={filter === item.id}
            data-testid={"structure-filter-" + item.id}
            onClick={() => onFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="structure-panel__search">
        <input
          type="search"
          className="structure-panel__search-input"
          placeholder="Najít vrstvu"
          aria-label="Najít vrstvu v projektu"
          value={query}
          onChange={(event) => onSearch(event.target.value)}
        />
        <small className="structure-panel__search-count">{countLayers(groups) + edges.length}</small>
      </div>

      <div className="structure-panel__page-list">
        {groups.map((group) => (
          <StructureLayerGroup
            key={group.id}
            group={group}
            empty={emptyOf(group.id)}
            collapsed={collapsed.includes(group.id)}
            onToggle={() => onToggleGroup(group.id)}
            onOpen={onOpenLayer}
          />
        ))}
        {edges.length > 0 && <StructureEdgeGroup edges={edges} onOpen={onOpenLayer} />}
      </div>
    </div>
  );
}
