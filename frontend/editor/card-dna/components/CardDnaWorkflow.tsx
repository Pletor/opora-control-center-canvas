import type { GraphEdge } from "@/shared/types/logic/types";
import type { Block } from "@/shared/desktop-state/logic/types";
import CardBlocks from "@/editor/canvas/node-card/components/CardBlocks";
import PipelineStageRow from "@/editor/workflow/card-pipeline/components/PipelineStageRow";
import { pipelineOf, pipelineSummary } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import type { CardDnaBranchProps } from "./CardDnaAssignment";

/** Workflow je auditní pohled: etapy jsou read-only, protože stávající karta je neupravovala inline. */
export default function CardDnaWorkflow({ node, data, state, graph }: CardDnaBranchProps) {
  const pipeline = pipelineOf(state, node.id); const summary = pipelineSummary(pipeline);
  const retries = pipeline.items.filter((stage) => stage.retryOf);
  const loops = repairLoops(pipeline.items.map((stage) => ({ id: stage.id, retryOf: stage.retryOf, status: stage.status })));
  const predecessors = related(graph.edges, graph.nodes, node.id, "before");
  const successors = related(graph.edges, graph.nodes, node.id, "after");
  const blocks = state.nodes[node.id]?.blocks ?? [];
  return <section className="card-dna__workflow" aria-label="Pipeline a workflow">
    <h3>Pipeline · {summary.finished}/{summary.total}</h3>
    <p>Etapy jsou zde jen ke čtení; jejich změny dosavadní karta dělá v editoru workflow, ne inline v DNA.</p>
    {pipeline.items.length ? <ol>{pipeline.items.map((stage, index) => <PipelineStageRow key={stage.id} stage={stage} first={index === 0} current={summary.current?.id === stage.id} disabled={true} onMove={() => undefined} onRemove={() => undefined} onSkip={() => undefined} onEdit={async () => false} />)}</ol> : <p>Pipeline zatím nemá etapy.</p>}
    <section><h3>Opakování a smyčky oprav</h3>{retries.length ? <ul>{retries.map((stage) => <li key={stage.id}>Opakování: {stage.title} · retryOf {stage.retryOf}</li>)}</ul> : <p>Žádné opakování etapy.</p>}
      {loops.length ? <ul>{loops.map((loop) => <li key={loop}>Smyčka oprav: {loop}</li>)}</ul> : <p>Smyčky oprav zatím nejsou zaznamenané.</p>}</section>
    <section><h3>Bloky, podmínky a porty</h3><CardBlocks showHandles={false} id={node.id} rows={data.view.rows} disabled={data.blocks.disabled} handlers={data.blocks} selectedBlockId={data.selectedBlockId} />
      {blocks.length ? <ul>{blocks.map((block) => <li key={block.id}>{block.number} · onMet: {branchLabel(block)}</li>)}</ul> : <p>Bloky nemají uložené workflow podmínky.</p>}</section>
    <Links title="Předchůdci" rows={predecessors} open={data.upstream?.open} />
    <Links title="Následníci" rows={successors} open={data.upstream?.open} />
  </section>;
}

function branchLabel(block: Block) {
  const branch = block.state.onMet;
  return branch.kind === "none" ? "bez akce" : `${branch.kind}${branch.targetId ? ` → ${branch.targetId}` : ""}${branch.note ? ` · ${branch.note}` : ""}`;
}
function repairLoops(items: { id: string; retryOf?: string; status: string }[]) {
  return items.filter((item) => item.retryOf).map((item) => `${item.retryOf} → ${item.id} (${item.status})`);
}
function related(edges: GraphEdge[], nodes: CardDnaBranchProps["graph"]["nodes"], nodeId: string, direction: "before" | "after") {
  return edges.filter((edge) => direction === "before" ? edge.target === nodeId : edge.source === nodeId).map((edge) => nodes.find((node) => node.id === (direction === "before" ? edge.source : edge.target))).filter((node): node is NonNullable<typeof node> => !!node);
}
function Links({ title, rows, open }: { title: string; rows: { id: string; name: string }[]; open?: (id: string) => void }) {
  return <section><h3>{title}</h3>{rows.length ? <ul>{rows.map((row) => <li key={row.id}>{open ? <button type="button" onClick={() => open(row.id)}>{row.name}</button> : row.name}</li>)}</ul> : <p>Žádné vazby.</p>}</section>;
}
