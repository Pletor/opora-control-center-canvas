// Rodič panelu Agenti a postupy: hlavička „Agenti a postupy“ s křížkem, záložky Katalog | Agenti |
// Hook a pod nimi jeden z dílků. Rodič nic neukládá sám — stav dostává v props z `useAgentNavbar`
// v App a každou změnu hlásí callbackem nahoru. O projektu, pracovním prostoru ani o druhu zdroje
// neví nic; panel je jeden pro celou aplikaci.
//
// Panel visí v zavěšeném panelu Editoru (`layout/panel-dock/`) a vyplní ho celý. Kreslí se, jen když
// je otevřený, proto se záložky ptají serveru rovnou a křížek v hlavičce ohlásí `onClose` nahoru.
import AgentNavbarCatalog from "@/layout/agent-navbar/components/AgentNavbarCatalog";
import AgentNavbarAgents from "@/layout/agent-navbar/components/AgentNavbarAgents";
import AgentControlPanel from "@/editor/agent-control/components/AgentControlPanel";
import "@/editor/agent-control/styles/agent-control.css";
import Icon from "@/ui-kit/icon/components/Icon";
import {
  AGENT_NAVBAR_TABS,
  AGENT_NAVBAR_TITLE,
  type AgentNavbarState,
  type AgentNavbarTab,
} from "@/layout/agent-navbar/logic/agent-navbar";
import {
  AGENT_CATEGORIES,
  agentItemsOf,
  searchAgentItems,
  type AgentCategory,
  type AgentItem,
} from "@/editor/component-library/agent-catalog/logic/agent-catalog";

export default function AgentNavbar({
  state,
  project,
  workspace,
  selectedNodeId = null,
  refreshKey = "",
  readOnly = false,
  items,
  onClose,
  onCategory,
  onSearch,
  onTab,
}: {
  state: AgentNavbarState;
  /** Adresa karty pro záložku Agenti; panel se na projekt ani prostředí nikdy neptá sám. */
  project: string;
  workspace: string;
  /** Karta, na kterou se ptá záložka Agenti; panel si ji nikdy nedohledává sám. */
  selectedNodeId?: string | null;
  /** Otisk plátna a revize plochy; změní se, když se karta pohne, a zadání se načte znovu. */
  refreshKey?: string;
  /** Parent truth for workspace/closed card read-only; Hook repeats server read-only after GET. */
  readOnly?: boolean;
  /** Celý katalog; jde předat kvůli testu, jinak platí obsah knihovny postupů. */
  items?: AgentItem[];
  /** Křížek v hlavičce: zavře zavěšený panel; co to znamená, rozhoduje rodič. */
  onClose: () => void;
  onCategory: (category: AgentCategory) => void;
  onSearch: (query: string) => void;
  onTab: (tab: AgentNavbarTab) => void;
}) {
  // Seznam se skládá tady, aby dílek dostal hotová data: nejdřív kategorie, pak hledání.
  // `agentItemsOf` bere `items` jako druhý argument — `undefined` z nepovinné props je stejné jako
  // vynechaný argument, takže test i běžný provoz sáhnou na stejnou výchozí knihovnu postupů.
  const inCategory = agentItemsOf(state.category, items);
  const found = searchAgentItems(inCategory, state.query);
  // Počet položek na kategorii (bez ohledu na hledání) pro řádek kategorie v katalogu — počítá se
  // tady, ne v dílku, aby katalog jen vypisoval hotová čísla.
  const categoryCounts = Object.fromEntries(
    AGENT_CATEGORIES.map((info) => [info.id, agentItemsOf(info.id, items).length]),
  ) as Record<AgentCategory, number>;
  return (
    <aside className="agent-navbar" aria-label={AGENT_NAVBAR_TITLE} data-testid="agent-navbar">
      <div className="agent-navbar__panel">
        <header className="agent-navbar__head">
          <span className="agent-navbar__head-text">
            <strong className="agent-navbar__title">{AGENT_NAVBAR_TITLE}</strong>
            <span className="agent-navbar__shortcut-hint">Ctrl+Shift+.</span>
          </span>
          <button
            type="button"
            className="agent-navbar__close"
            aria-label="Zavřít Agenty a postupy"
            title="Zavřít Agenty a postupy (Esc)"
            data-testid="agent-navbar-close"
            onClick={onClose}
          >
            <Icon name="x" size={16} />
          </button>
        </header>

        <nav className="agent-navbar__tabs" role="tablist" aria-label="Záložky pravého panelu">
          {AGENT_NAVBAR_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className={"agent-navbar__tab" + (state.tab === tab.id ? " agent-navbar__tab--active" : "")}
              aria-selected={state.tab === tab.id}
              data-testid={"agent-tab-" + tab.id}
              onClick={() => onTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {state.tab === "agents" ? (
          <AgentNavbarAgents
            project={project}
            workspace={workspace}
            selectedNodeId={selectedNodeId}
            refreshKey={refreshKey}
          />
        ) : state.tab === "hook" ? (
          <AgentControlPanel
            active
            project={project}
            workspace={workspace}
            selectedNodeId={selectedNodeId}
            readOnly={readOnly}
          />
        ) : (
          <AgentNavbarCatalog
            items={found}
            category={state.category}
            categoryCounts={categoryCounts}
            query={state.query}
            onCategory={onCategory}
            onSearch={onSearch}
          />
        )}
      </div>
    </aside>
  );
}
