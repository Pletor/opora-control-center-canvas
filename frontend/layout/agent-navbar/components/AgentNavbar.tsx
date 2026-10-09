// Rodič sekcí Agenti a Postupy (docs/menu-a-katalog.md, část A): oba jsou pohled na jeden katalog,
// jen každý ukáže své kategorie. Agenti mají záložky Katalog | Vybraná karta | Kód, Postupy jsou
// jen katalog postupů a pipeline. Rodič nic neukládá sám — stav dostává v props z `useAgentNavbar`
// v App a každou změnu hlásí callbackem nahoru. Projekt zná jen přes hotový `profile` z App
// (docs/suplik-a-profil.md), podle kterého se katalog zúží; druh zdroje ani nastavení nečte.
//
// Panel leží v menu u levého okraje (`layout/panel-dock/`) a vyplní ho pod hlavičkou projektu.
// Vlastní hlavičku ani křížek nemá: jednu hlavičku nese rám sekce, zavírá se ikonou nebo ☰.
import AgentNavbarCatalog from "@/layout/agent-navbar/components/AgentNavbarCatalog";
import AgentNavbarAgents from "@/layout/agent-navbar/components/AgentNavbarAgents";
import AgentControlPanel from "@/editor/agent-control/components/AgentControlPanel";
import "@/editor/agent-control/styles/agent-control.css";
import CatalogScopeBar from "@/layout/panel-dock/components/CatalogScopeBar";
import CatalogOutsideRow from "@/layout/panel-dock/components/CatalogOutsideRow";
import type { CatalogScope } from "@/layout/panel-dock/logic/panel-drawer";
import { agentView } from "@/layout/agent-navbar/logic/agent-scope";
import { outsideSummary } from "@/editor/component-library/library-catalog/logic/catalog-fit";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import {
  AGENT_NAVBAR_TABS,
  AGENT_SECTION_TITLE,
  sectionCategories,
  type AgentNavbarState,
  type AgentNavbarTab,
  type AgentSection,
} from "@/layout/agent-navbar/logic/agent-navbar";
import type { AgentCategory, AgentItem } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import "@/layout/agent-navbar/styles/agent-navbar.css";

const NO_PROFILE: ProjectProfile = { architecture: "", tenancy: "", platform: "web" };

export default function AgentNavbar({
  section,
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
  onCategory,
  onSearch,
  onTab,
}: {
  /** Kterou sekci menu panel kreslí; rozhoduje rodič podle ikony v liště. */
  section: AgentSection;
  state: AgentNavbarState;
  /** Adresa karty pro záložku Vybraná karta; panel se na projekt ani prostředí nikdy neptá sám. */
  project: string;
  workspace: string;
  /** Karta, na kterou se ptá záložka Vybraná karta; panel si ji nikdy nedohledává sám. */
  selectedNodeId?: string | null;
  /** Otisk plátna a revize plochy; změní se, když se karta pohne, a zadání se načte znovu. */
  refreshKey?: string;
  /** Rodičovská pravda o read-only ploše či uzavřené kartě; Hook po GET zopakuje i read-only ze serveru. */
  readOnly?: boolean;
  /** Celý katalog; jde předat kvůli testu, jinak platí obsah knihovny postupů. */
  items?: AgentItem[];
  /** Profil projektu od App; podle něj se katalog zúží. Bez profilu se nic nefiltruje. */
  profile?: ProjectProfile;
  scope?: CatalogScope;
  showOutside?: boolean;
  onScope?: (scope: CatalogScope) => void;
  onToggleOutside?: () => void;
  onCategory: (section: AgentSection, category: AgentCategory) => void;
  onSearch: (section: AgentSection, query: string) => void;
  onTab: (tab: AgentNavbarTab) => void;
}) {
  const own = state[section];
  const categories = sectionCategories(section);
  // Postupy záložky nemají: jsou vždy katalog. Agenti ukážou záložku, kterou uživatel nechal.
  const tab: AgentNavbarTab = section === "agents" ? state.tab : "catalog";
  // Seznam se skládá tady, aby dílek dostal hotová data: kategorie, profil projektu, hledání a čísla
  // u kategorií. Pravidla drží `agentView`; `items` jde předat kvůli testu, jinak platí celý katalog.
  const view = agentView(own.category, profile, { scope, showOutside, query: own.query }, items);
  const outsideRow = view.outside.length > 0 && scope === "fitting" && !own.query.trim();
  return (
    <aside className="agent-navbar" aria-label={AGENT_SECTION_TITLE[section]} data-testid={"agent-navbar-" + section}>
      <div className="agent-navbar__panel">
        {section === "agents" && (
          <nav className="agent-navbar__tabs" role="tablist" aria-label="Záložky Agentů">
            {AGENT_NAVBAR_TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                className={"agent-navbar__tab" + (tab === item.id ? " agent-navbar__tab--active" : "")}
                aria-selected={tab === item.id}
                data-testid={"agent-tab-" + item.id}
                onClick={() => onTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>
        )}

        {tab === "agents" ? (
          <AgentNavbarAgents
            project={project}
            workspace={workspace}
            selectedNodeId={selectedNodeId}
            refreshKey={refreshKey}
          />
        ) : tab === "code" ? (
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
            category={own.category}
            categories={categories}
            categoryCounts={view.counts}
            notes={view.notes}
            outside={view.outsideIds}
            filter={view.filtering && onScope ? (
              <CatalogScopeBar scope={scope} fitting={view.fittingCount} all={view.allCount} onScope={onScope} />
            ) : null}
            footer={outsideRow && onToggleOutside ? (
              <CatalogOutsideRow summary={outsideSummary(view.outside, ["prvek", "prvky", "prvků"])} shown={showOutside} onToggle={onToggleOutside} />
            ) : null}
            query={own.query}
            onCategory={(category) => onCategory(section, category)}
            onSearch={(query) => onSearch(section, query)}
          />
        )}
      </div>
    </aside>
  );
}
