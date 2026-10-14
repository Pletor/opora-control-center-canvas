import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { BoardIndex } from "@/editor/canvas/board/logic/board-index";

/** Co do karty přitéká z předchozích karet. S indexem plátna (`BoardIndex`) bez průchodu všemi hranami,
 *  uzly a rozhodnutími pro každou kartu; výsledek je stejný jako bez něj. */
export function upstreamRows(graph: Graph, state: DesktopState, nodeId: string, index?: BoardIndex) {
  const incoming = index ? index.incoming.get(nodeId) ?? [] : graph.edges.filter(edge => edge.target === nodeId && edge.port !== "flow");
  const nodeOf = (id: string) => index ? index.byId.get(id) : graph.nodes.find(node => node.id === id);
  const decisionsOf = (id: string) => index ? index.decisionsByNode.get(id) ?? [] : state.decisions.filter(d => d.nodeId === id);
  const isSuperseded = (id: string) => index ? index.superseded.has(id) : state.decisions.some(next => next.supersedes === id);
  return incoming.flatMap(edge => {
    const source = nodeOf(edge.source);
    if (!source) return [];
    const blocks = state.nodes[source.id]?.blocks ?? [];
    const port = blocks.find(b => b.id === edge.sourceBlockId)?.ports?.find(p => p.id === edge.sourcePortId);
    const chosen = blocks.flatMap(b => b.ports ?? []).filter(p => p.status === "chosen");
    const report = state.edges?.[edge.id];
    const decisions = decisionsOf(source.id);
    return [{ edgeId: edge.id, nodeId: source.id, name: source.name,
      assumptionChanged: decisions.some(d => !!d.supersedes),
      label: port?.label || chosen.map(p => p.label).join(", "), rejected: port?.status === "rejected",
      details: [port?.reason, ...chosen.filter(p => p !== port).map(p => `${p.label}: ${p.reason}`),
        ...decisions.map(d => `${isSuperseded(d.id) ? "Nahrazeno: " : d.supersedes ? "Oprava: " : ""}${d.text}`),
        report?.summary, report?.handoff, report?.errors].filter(Boolean).join("\n") }];
  });
}
export type UpstreamRow = ReturnType<typeof upstreamRows>[number];
