// Rodič sekce Struktura v menu Editoru: nahoře přepínač dvou záložek „Struktura | Vybraná karta“
// a pod ním vždy jen jeden obsah s vlastním posunem, takže se nic nepřekrývá. Struktura = strom vrstev
// projektu (filtr, hledání, sbalitelné skupiny) a akce kostry; Vybraná karta = co agent vybrané karty
// dostane. Výběr karty na plátně záložku sám nepřepíná. Rodič nic neukládá: stav (i záložku) dostává
// v props z `useStructurePanel` v App, akce a blok karty hotové jako dílky a každou změnu hlásí callbackem.
import type { ReactNode } from "react";
import StructureTree from "@/layout/structure-panel/components/StructureTree";
import { STRUCTURE_TABS, type StructureState, type StructureTab } from "@/layout/structure-panel/logic/structure-panel";
import type { LayerFilter, LayerGroupId } from "@/layout/structure-panel/logic/layer-list";
import type { IndexMatches } from "@/layout/structure-panel/logic/canvas-index";
import type { CanvasNode } from "@/shared/types/logic/types";
import "@/layout/structure-panel/styles/structure-panel.css";

export default function StructurePanel({ state, nodes, closed, matches, actions, selectedCard, onTab, onFilter, onSearch, onToggleGroup, onOpenLayer }: {
  state: StructureState;
  /** Celý graf projektu; panel si ho nikdy nenačítá sám. */
  nodes: CanvasNode[];
  /** Id uzavřených karet (`done.confirmed`) pro značku „skryto“. */
  closed: ReadonlySet<string>;
  /** Shody indexu plátna pro hledání; `null` = lokální filtr podle názvu. */
  matches: IndexMatches | null;
  /** Akce kostry (dílek `editor/skeleton`). */
  actions?: ReactNode;
  /** Obsah záložky „Vybraná karta“ (dílek `layout/card-brief`). */
  selectedCard: ReactNode;
  onTab: (tab: StructureTab) => void;
  onFilter: (filter: LayerFilter) => void;
  onSearch: (query: string) => void;
  onToggleGroup: (group: LayerGroupId) => void;
  /** Klik na vrstvu; co se stane (vstup do vrstvy a výběr karty), rozhoduje rodič. */
  onOpenLayer: (id: string) => void;
}) {
  return (
    <aside className="structure-panel" aria-label="Struktura" data-testid="structure-panel">
      <nav className="structure-panel__tabs" role="tablist" aria-label="Záložky Struktury">
        {STRUCTURE_TABS.map((item) => (
          <button key={item.id} type="button" role="tab" id={"structure-tab-" + item.id}
            className={"structure-panel__tab" + (state.tab === item.id ? " structure-panel__tab--active" : "")}
            aria-selected={state.tab === item.id} aria-controls={"structure-pane-" + item.id}
            data-testid={"structure-tab-" + item.id} onClick={() => onTab(item.id)}>
            {item.label}
          </button>
        ))}
      </nav>
      {state.tab === "tree" ? (
        <div className="structure-panel__pane" role="tabpanel" id="structure-pane-tree" aria-labelledby="structure-tab-tree">
          <StructureTree nodes={nodes} closed={closed} matches={matches} filter={state.filter} query={state.query}
            collapsed={state.collapsed} onFilter={onFilter} onSearch={onSearch} onToggleGroup={onToggleGroup} onOpenLayer={onOpenLayer} />
          {actions}
        </div>
      ) : (
        <div className="structure-panel__pane structure-panel__pane--card" role="tabpanel" id="structure-pane-card" aria-labelledby="structure-tab-card">
          {selectedCard}
        </div>
      )}
    </aside>
  );
}
