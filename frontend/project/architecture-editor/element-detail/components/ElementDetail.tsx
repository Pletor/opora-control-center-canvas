import { useMemo, useState } from "react";
import type { CanvasNode, EdgeCarries, Graph, PageSite } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import StructureIcon from "../../component-structure/components/StructureIcon";
import { toneOf } from "../../component-structure/logic/structure-model";
import { agentContext, nodeLinks } from "../logic/agent-context";
import { journeysOfPage } from "../../domain-map/logic/page-journeys";
import { sectionChoice } from "../logic/section-choice";
import { whyChain, whyChainText } from "../logic/why-chain";
import { useNodeSpec } from "../logic/use-node-spec";
import AgentContextPanel from "./AgentContextPanel";
import BriefTab from "./BriefTab";
import LinkList from "./LinkList";
import PageTab from "./PageTab";
import SectionPicker from "./SectionPicker";
import WorkTab from "./WorkTab";
import "../styles/element-detail.css";

export type ElementDetailProps = {
  project: string;
  workspace: string;
  graph: Graph;
  nodeId: string;
  domainId: string;
  phase: NodePhase;
  done: boolean;
  disabled: boolean;
  onIdentity: (original: CanvasNode, name: string, purpose: string) => Promise<void>;
  onOpenEditor: (id: string) => void;
  onSelect: (id: string) => void;
  /** Člověk určil, co po vazbě `next` teče; `null` = neurčeno. Ukládá rodič. */
  onCarries: (edgeId: string, carries: EdgeCarries | null) => void;
  /** Člověk určil, kterou sekci stránky komponenta realizuje; `null` = neurčeno. Ukládá rodič. */
  onSection: (nodeId: string, section: string | null) => void;
  /** Člověk uložil záměr a sekce vybrané stránky (záložka Stránka); `original` je stránka, ze které koncept vznikl. Ukládá rodič. */
  onPage: (original: CanvasNode, site: PageSite) => Promise<void>;
  onClose: () => void;
};

type Tab = "page" | "brief" | "links" | "work";
const TABS: { id: Tab; label: string }[] = [
  { id: "page", label: "Stránka" },
  { id: "brief", label: "Zadání" },
  { id: "links", label: "Vazby" },
  { id: "work", label: "Práce" },
];

/** Pravý sloupec Editoru stránky: kontext agenta a záložky nad jedním prvkem (u stránky navíc a jako první Stránka). Nic neukládá sám. */
export default function ElementDetail(props: ElementDetailProps) {
  const { project, workspace, graph, nodeId, domainId, phase, done, disabled, onIdentity, onOpenEditor, onSelect, onCarries, onSection, onPage, onClose } = props;
  const [chosen, setChosen] = useState<Tab | null>(null);
  const node = graph.nodes.find((item) => item.id === nodeId) ?? null;
  const page = node?.site?.kind === "page" ? node as CanvasNode & { site: PageSite } : null;
  // Stránka otevírá svou záložku Stránka; jiný prvek ji nemá a spadne na Zadání.
  const tab: Tab = chosen === "page" && !page ? "brief" : chosen ?? (page ? "page" : "brief");
  const tabs = page ? TABS : TABS.filter((item) => item.id !== "page");
  const context = useMemo(() => agentContext(graph, nodeId, domainId), [graph, nodeId, domainId]);
  const links = useMemo(() => nodeLinks(graph, nodeId), [graph, nodeId]);
  const section = useMemo(() => sectionChoice(graph, nodeId), [graph, nodeId]);
  const why = useMemo(() => whyChain(graph, nodeId), [graph, nodeId]);
  const roles = useMemo(() => {
    const domain = graph.nodes.find((item) => item.id === domainId);
    return page && domain?.site?.kind === "application" ? journeysOfPage(domain.site, page.id) : [];
  }, [graph, domainId, page]);
  const spec = useNodeSpec(project, workspace, nodeId);

  return (
    <aside className="element-detail" aria-label="Detail prvku">
      <header className="element-detail__head">
        <h2 className="element-detail__heading">Detail prvku</h2>
        <button type="button" className="element-detail__close" aria-label="Zavřít detail prvku" onClick={onClose}>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </header>
      {node ? (
        <div className="element-detail__body">
          <AgentContextPanel context={context} />
          {section ? <SectionPicker choice={section} disabled={disabled} onSection={(value) => onSection(nodeId, value)} /> : null}
          {why ? <p className="element-detail__why" data-testid="element-detail-why"><span className="element-detail__why-label">Proč</span> {whyChainText(why)}</p> : null}
          <div className={`element-detail__identity element-detail__identity--${toneOf(node)}`}>
            <StructureIcon name={node.kind === "sector" ? "sector" : toneOf(node)} className="element-detail__icon" />
            <div className="element-detail__identity-text">
              <h3 className="element-detail__name">{node.name.trim() || "Bez názvu"}</h3>
              <p className="element-detail__purpose">{node.purpose.trim() || "Účel zatím nic"}</p>
            </div>
          </div>
          <div className="element-detail__tabs" role="tablist" aria-label="Části detailu">
            {tabs.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={`element-detail__tab${tab === item.id ? " element-detail__tab--active" : ""}`}
                onClick={() => setChosen(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {tab === "page" && page ? <PageTab key={page.id} page={page} roles={roles} disabled={disabled} onSave={onPage} /> : null}
          {tab === "brief" ? (
            <BriefTab
              node={node}
              spec={spec}
              phase={phase}
              done={done}
              disabled={disabled}
              onIdentity={onIdentity}
            />
          ) : null}
          {tab === "links" ? (
            <div className="element-detail__pane">
              <LinkList title="Příchozí vazby" links={links.incoming} empty="Žádná příchozí vazba" onSelect={onSelect} onCarries={onCarries} disabled={disabled} />
              <LinkList title="Odchozí vazby" links={links.outgoing} empty="Žádná odchozí vazba" onSelect={onSelect} onCarries={onCarries} disabled={disabled} />
            </div>
          ) : null}
          {tab === "work" ? <WorkTab nodeId={nodeId} phase={phase} done={done} onOpenEditor={onOpenEditor} /> : null}
        </div>
      ) : (
        <p className="element-detail__muted">Prvek je nedostupný.</p>
      )}
    </aside>
  );
}
