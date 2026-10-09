import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

export function upstreamRows(graph: Graph, state: DesktopState, nodeId: string) {
  return graph.edges.filter(edge => edge.target === nodeId && edge.port !== "flow").flatMap(edge => {
    const source = graph.nodes.find(node => node.id === edge.source);
    if (!source) return [];
    const blocks = state.nodes[source.id]?.blocks ?? [];
    const port = blocks.find(b => b.id === edge.sourceBlockId)?.ports?.find(p => p.id === edge.sourcePortId);
    const chosen = blocks.flatMap(b => b.ports ?? []).filter(p => p.status === "chosen");
    const report = state.edges?.[edge.id];
    return [{ edgeId: edge.id, nodeId: source.id, name: source.name,
      assumptionChanged: state.decisions.some(d => d.nodeId === source.id && !!d.supersedes),
      label: port?.label || chosen.map(p => p.label).join(", "), rejected: port?.status === "rejected",
      details: [port?.reason, ...chosen.filter(p => p !== port).map(p => `${p.label}: ${p.reason}`),
        ...state.decisions.filter(d => d.nodeId === source.id).map(d => `${state.decisions.some(next => next.supersedes === d.id) ? "Nahrazeno: " : d.supersedes ? "Oprava: " : ""}${d.text}`),
        report?.summary, report?.handoff, report?.errors].filter(Boolean).join("\n") }];
  });
}
export type UpstreamRow = ReturnType<typeof upstreamRows>[number];
