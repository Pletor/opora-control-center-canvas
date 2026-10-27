import { useMemo, useState } from "react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import StructureIcon from "../../component-structure/components/StructureIcon";
import { toneOf } from "../../component-structure/logic/structure-model";
import { agentContext, nodeLinks } from "../logic/agent-context";
import { useNodeSpec } from "../logic/use-node-spec";
import AgentContextPanel from "./AgentContextPanel";
import BriefTab from "./BriefTab";
import LinkList from "./LinkList";
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
  onClose: () => void;
};

type Tab = "brief" | "links" | "work";
const TABS: { id: Tab; label: string }[] = [
  { id: "brief", label: "Zadání" },
  { id: "links", label: "Vazby" },
  { id: "work", label: "Práce" },
];

/** Pravý sloupec Editoru stránky: kontext agenta a tři záložky nad jedním prvkem. Nic neukládá sám. */
export default function ElementDetail(props: ElementDetailProps) {
  const { project, workspace, graph, nodeId, domainId, phase, done, disabled, onIdentity, onOpenEditor, onSelect, onClose } = props;
  const [tab, setTab] = useState<Tab>("brief");
  const node = graph.nodes.find((item) => item.id === nodeId) ?? null;
  const context = useMemo(() => agentContext(graph, nodeId, domainId), [graph, nodeId, domainId]);
  const links = useMemo(() => nodeLinks(graph, nodeId), [graph, nodeId]);
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
          <div className={`element-detail__identity element-detail__identity--${toneOf(node)}`}>
            <StructureIcon name={node.kind === "sector" ? "sector" : toneOf(node)} className="element-detail__icon" />
            <div className="element-detail__identity-text">
              <h3 className="element-detail__name">{node.name.trim() || "Bez názvu"}</h3>
              <p className="element-detail__purpose">{node.purpose.trim() || "Účel zatím nic"}</p>
            </div>
          </div>
          <div className="element-detail__tabs" role="tablist" aria-label="Části detailu">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={`element-detail__tab${tab === item.id ? " element-detail__tab--active" : ""}`}
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
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
              <LinkList title="Příchozí vazby" links={links.incoming} empty="Žádná příchozí vazba" onSelect={onSelect} />
              <LinkList title="Odchozí vazby" links={links.outgoing} empty="Žádná odchozí vazba" onSelect={onSelect} />
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
