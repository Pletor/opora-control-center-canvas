// Rodič panelu Agenti a postupy: hlavička „Agenti a postupy“ s křížkem, záložky Katalog | Agenti |
// Hook a pod nimi jeden z dílků. Rodič nic neukládá sám — stav dostává v props z `useAgentNavbar`
// v App a každou změnu hlásí callbackem nahoru. Projekt zná jen přes hotový `profile` z App
// (docs/suplik-a-profil.md), podle kterého se katalog zúží; druh zdroje ani nastavení nečte.
//
// Panel leží v šuplíku u levého okraje (`layout/panel-dock/`) a vyplní ho pod hlavičkou projektu.
// Kreslí se, jen když je otevřený, proto se záložky ptají serveru rovnou a křížek ohlásí `onClose`.
import AgentNavbarCatalog from "@/layout/agent-navbar/components/AgentNavbarCatalog";
import AgentNavbarAgents from "@/layout/agent-navbar/components/AgentNavbarAgents";
import AgentControlPanel from "@/editor/agent-control/components/AgentControlPanel";
import "@/editor/agent-control/styles/agent-control.css";
import Icon from "@/ui-kit/icon/components/Icon";
import CatalogScopeBar from "@/layout/panel-dock/components/CatalogScopeBar";
import CatalogOutsideRow from "@/layout/panel-dock/components/CatalogOutsideRow";
import type { CatalogScope } from "@/layout/panel-dock/logic/panel-drawer";
import { agentView } from "@/layout/agent-navbar/logic/agent-scope";
import { outsideSummary } from "@/editor/component-library/library-catalog/logic/catalog-fit";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import {
  AGENT_NAVBAR_TABS,
  AGENT_NAVBAR_TITLE,
  type AgentNavbarState,
  type AgentNavbarTab,
} from "@/layout/agent-navbar/logic/agent-navbar";
import type { AgentCategory, AgentItem } from "@/editor/component-library/agent-catalog/logic/agent-catalog";

const NO_PROFILE: ProjectProfile = { architecture: "", tenancy: "", platform: "web" };

export default function AgentNavbar({
  state,
  project,
  workspace,
  selectedNodeId = null,
  refreshKey = "",
  readOnly = false,
  items,
  profile = NO_PROFILE,
  scope = "fitting",
  showOutside = false,
  onScope,
  onToggleOutside,
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
  /** Profil projektu od App; podle něj se katalog zúží. Bez profilu se nic nefiltruje. */
  profile?: ProjectProfile;
  scope?: CatalogScope;
  showOutside?: boolean;
  onScope?: (scope: CatalogScope) => void;
  onToggleOutside?: () => void;
  /** Křížek v hlavičce: zavře šuplík; co to znamená, rozhoduje rodič. */
  onClose: () => void;
  onCategory: (category: AgentCategory) => void;
  onSearch: (query: string) => void;
  onTab: (tab: AgentNavbarTab) => void;
}) {
  // Seznam se skládá tady, aby dílek dostal hotová data: kategorie, profil projektu, hledání a čísla
  // u kategorií. Pravidla drží `agentView`; `items` jde předat kvůli testu, jinak platí celý katalog.
  const view = agentView(state.category, profile, { scope, showOutside, query: state.query }, items);
  const outsideRow = view.outside.length > 0 && scope === "fitting" && !state.query.trim();
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
            items={view.shown}
            category={state.category}
            categoryCounts={view.counts}
            notes={view.notes}
            outside={view.outsideIds}
            filter={view.filtering && onScope ? (
              <CatalogScopeBar scope={scope} fitting={view.fittingCount} all={view.allCount} onScope={onScope} />
            ) : null}
            footer={outsideRow && onToggleOutside ? (
              <CatalogOutsideRow summary={outsideSummary(view.outside, ["postup", "postupy", "postupů"])} shown={showOutside} onToggle={onToggleOutside} />
            ) : null}
            query={state.query}
            onCategory={onCategory}
            onSearch={onSearch}
          />
        )}
      </div>
    </aside>
  );
}
