import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import type { GraphProposal } from "../logic/graph-proposals";
import { proposalFocus, proposalPreview } from "../logic/proposal-preview";
import { fieldKeys, fieldLabels } from "@/hub/plan-changes/logic/plan-changes";
import { CARRIES_LABEL } from "@/shared/edge-carries/logic/edge-carries";

/** Snapshot renderer: selection and zoom stay local; this component has no mutation callbacks. */
export default function GraphProposalCanvas({ proposal }: { proposal: GraphProposal }) {
  const [selected, select] = useState("");
  const graph = useMemo(() => proposalPreview(proposal), [proposal]);
  const initialFit = useMemo(() => ({ padding: 0.2, nodes: proposalFocus(proposal) }), [proposal]);
  const additions = new Set(proposal.additions.nodes.map(node => node.id));
  const nodes = useMemo(() => graph?.nodes.map(node => ({ id: node.id,
    position: { x: node.x, y: node.y }, data: { label: <><strong>{node.name}</strong><small>{node.kind} · {node.id}</small></> },
    className: additions.has(node.id) ? "graph-proposals__preview-node--new" : "",
    style: { width: 240 }, selected: node.id === selected })) ?? [], [graph, selected, proposal]);
  const edges = useMemo(() => graph?.edges.map(edge => ({ id: edge.id, source: edge.source, target: edge.target,
    label: `${edge.port ?? "next"}${edge.carries ? ` · ${CARRIES_LABEL[edge.carries]}` : ""}` })) ?? [], [graph]);
  if (!graph) return <p role="alert">Uložený výsledný graf chybí. Náhled změn nelze bezpečně sestavit.</p>;
  const node = graph.nodes.find(item => item.id === selected);
  const spec = [...proposal.specifications, ...proposal.adoptionDocuments, ...(proposal.architectureDocuments ?? [])].find(item => item.nodeId === selected);
  return <section aria-label="Plátno návrhu" className="graph-proposals__preview">
    <p>Uložený návrh · {graph.nodes.length} prvků · {graph.edges.length} vazeb. Kliknutím otevřete detail. Přijatý plán se nemění.</p>
    <div className="graph-proposals__preview-canvas">
      <ReactFlow key={proposal.id} nodes={nodes} edges={edges} nodesDraggable={false} nodesConnectable={false}
        edgesReconnectable={false} deleteKeyCode={null} fitView fitViewOptions={initialFit}
        onNodeClick={(_, item) => select(item.id)} onPaneClick={() => select("")} minZoom={0.05} maxZoom={1.5}>
        <Background /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
    {node && <article className="graph-proposals__preview-detail" aria-label="Detail prvku návrhu">
      <h4>{node.name}</h4><p>ID <code>{node.id}</code> · rodič <code>{node.parentId ?? "kořen"}</code></p>
      {node.purpose && <p>{node.purpose}</p>}
      {spec ? fieldKeys.map(field => <div key={field}><strong>{fieldLabels[field]}</strong><pre>{spec.fields[field] || "(prázdné)"}</pre></div>)
        : <p>Návrh pro tento prvek neobsahuje nové zadání.</p>}
    </article>}
  </section>;
}
