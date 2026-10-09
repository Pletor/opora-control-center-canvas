import type { Graph, GraphEdge } from "@/shared/types/logic/types";
import type { Block } from "@/shared/desktop-state/logic/types";

export function branchLabel(block: Block) {
  const branch = block.state.onMet;
  return branch.kind === "none" ? "bez akce" : `${branch.kind}${branch.targetId ? ` → ${branch.targetId}` : ""}${branch.note ? ` · ${branch.note}` : ""}`;
}

export function repairLoops(items: { id: string; retryOf?: string; status: string }[]) {
  return items.filter((item) => item.retryOf).map((item) => `${item.retryOf} → ${item.id} (${item.status})`);
}

export function relatedNodes(edges: GraphEdge[], nodes: Graph["nodes"], nodeId: string, direction: "before" | "after") {
  return edges.filter((edge) => direction === "before" ? edge.target === nodeId : edge.source === nodeId)
    .map((edge) => nodes.find((node) => node.id === (direction === "before" ? edge.source : edge.target)))
    .filter((node): node is Graph["nodes"][number] => !!node);
}
