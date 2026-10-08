import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import CardBody from "@/editor/canvas/node-card/components/CardBody";
import CardBlocks from "@/editor/canvas/node-card/components/CardBlocks";
import CardFacts from "@/editor/canvas/node-card/components/CardFacts";
import CardRules from "@/editor/canvas/node-card/components/CardRules";
import InheritedRules from "@/editor/canvas/node-card/components/InheritedRules";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import NodeSpecHistory from "./NodeSpecHistory";

export type CardDnaBranchProps = {
  node: CanvasNode; data: NodeCardData; state: DesktopState; graph: Graph;
  project?: string; workspace?: string; onSaveNode?: (node: CanvasNode) => void;
};

/** Zadání skládá původní editory až uvnitř DNA záložky; historie se tím načte až po jejím mountu. */
export default function CardDnaAssignment({ node, data, state, graph: _graph, project, workspace }: CardDnaBranchProps) {
  const canLoad = !!project && !!workspace;
  const decisions = state.decisions.filter((decision) => decision.nodeId === node.id);
  return <section className="card-dna__assignment" aria-label="Zadání karty">
    <h3>Zadání</h3>
    {canLoad ? <>
      <NodeSpecEditor project={project} workspace={workspace} nodeId={node.id} disabled={data.blocks.disabled} />
      <NodeSpecHistory project={project} workspace={workspace} nodeId={node.id} />
      <NodeTextEditor project={project} workspace={workspace} node={node.id} />
    </> : <p role="status">Zadání, historie revizí i text vyžadují vybraný projekt a pracovní prostor.</p>}
    <section><h3>Název a podstata</h3><CardBody id={node.id} name={data.view.name} purpose={data.view.purpose} rename={data.rename} /></section>
    <section><h3>Bloky, podmínky a porty</h3>
      <CardBlocks showHandles={false} id={node.id} rows={data.view.rows} disabled={data.blocks.disabled} handlers={data.blocks} selectedBlockId={data.selectedBlockId} />
    </section>
    {data.facts && <CardFacts facts={data.facts} />}
    <section><h3>Pravidla</h3>
      {data.rules?.items.length ? <CardRules rules={data.rules.items} write={data.rules.write} disabled={data.blocks.disabled} /> : <p>Vlastní pravidla zatím nejsou.</p>}
      {data.inheritedRules?.length ? <InheritedRules rules={data.inheritedRules} /> : <p>Žádné zděděné pravidlo.</p>}
    </section>
    <section><h3>Rozhodnutí</h3>{decisions.length ? <ol>{decisions.map((decision) => <li key={decision.id}><time>{decision.createdAt || "čas nezaznamenán"}</time> · {decision.by}: {decision.text}</li>)}</ol> : <p>Žádné rozhodnutí.</p>}</section>
  </section>;
}
