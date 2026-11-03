// Rozdíl dvou verzí grafu (n8n ho v historii verzí nemá): uzly přidané, odebrané a změněné (typ, verze typu,
// parametry, připnutý výstup; samotný posun polohy změnou není) a hrany přidané a odebrané. Uzly se párují podle
// stálého id, hrany podle koncových bodů, ne podle id.
import type { FlowEdge, FlowGraph, FlowNode } from "./flow-types";

export type NodeMark = "added" | "removed" | "changed";
export type GraphDiff = {
  nodes: ReadonlyMap<string, NodeMark>; addedEdges: FlowEdge[]; removedEdges: FlowEdge[];
  /** Uzly základu, které v nové verzi chybí: plátno je ukáže jako duchy. */
  ghosts: FlowNode[];
};

const stable = (value: unknown): string => JSON.stringify(value, (_key, v) => v && typeof v === "object" && !Array.isArray(v)
  ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b))) : v) ?? "";
const nodeKey = (node: FlowNode) => stable([node.type, node.type_version ?? 1, node.params ?? {}, node.pinned_output ?? null]);
const edgeKey = (edge: FlowEdge) => [edge.source_node, edge.source_port, edge.target_node, edge.target_port].join("|");

/** `base` = starší verze, `next` = zobrazená. */
export function graphDiff(base: FlowGraph, next: FlowGraph): GraphDiff {
  const marks = new Map<string, NodeMark>();
  const before = new Map(base.nodes.map((node) => [node.id, node]));
  for (const node of next.nodes) {
    const old = before.get(node.id);
    if (!old) marks.set(node.id, "added");
    else if (nodeKey(old) !== nodeKey(node)) marks.set(node.id, "changed");
  }
  const ghosts = base.nodes.filter((node) => !next.nodes.some((item) => item.id === node.id));
  for (const ghost of ghosts) marks.set(ghost.id, "removed");
  const baseEdges = new Set(base.edges.map(edgeKey)), nextEdges = new Set(next.edges.map(edgeKey));
  return { nodes: marks, ghosts, addedEdges: next.edges.filter((e) => !baseEdges.has(edgeKey(e))), removedEdges: base.edges.filter((e) => !nextEdges.has(edgeKey(e))) };
}

export function diffSummary(diff: GraphDiff): string {
  const count = (mark: NodeMark) => [...diff.nodes.values()].filter((item) => item === mark).length;
  const parts = [`+${count("added")} uzlů`, `−${count("removed")}`, `~${count("changed")} změněno`, `vazby +${diff.addedEdges.length}/−${diff.removedEdges.length}`];
  return parts.join(" · ");
}
