import type { Graph, CanvasNode } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

export function nearestSector(graph: Graph, node: CanvasNode): string | null {
  let cursor = node.parentId;
  const seen = new Set<string>();
  while (cursor && !seen.has(cursor)) {
    seen.add(cursor);
    const parent = graph.nodes.find(n => n.id === cursor);
    if (parent?.kind === "sector") return parent.id;
    cursor = parent?.parentId ?? null;
  }
  return null;
}

export function sectorViews(graph: Graph, state: DesktopState) {
  const result: Record<string, { closed: number; total: number; verified: boolean; gateName: string; blockedBy: string[] }> = {};
  for (const sector of graph.nodes.filter(n => n.kind === "sector")) {
    const members = graph.nodes.filter(n => {
      if (n.kind !== "node") return false;
      let cursor = n.parentId;
      const seen = new Set<string>();
      while (cursor && !seen.has(cursor)) {
        if (cursor === sector.id) return true;
        seen.add(cursor); cursor = graph.nodes.find(p => p.id === cursor)?.parentId ?? null;
      }
      return false;
    });
    const closed = members.filter(n => state.nodes[n.id]?.done?.confirmed).length;
    const gate = sector.gateNodeId ? state.nodes[sector.gateNodeId]?.done : undefined;
    const scenario = graph.nodes.find(n => n.id === sector.gateNodeId)?.scenario;
    const run = sector.gateNodeId ? state.nodes[sector.gateNodeId]?.scenarioRun : undefined;
    const scenarioReady = !scenario || (run?.command === scenario.command && run?.failed === 0);
    const own = state.nodes[sector.id]?.done;
    const allClosed = members.length > 0 && closed === members.length;
    result[sector.id] = { closed, total: members.length,
      verified: sector.gateNodeId ? !!gate?.confirmed && gate.by === "human" && allClosed && scenarioReady
        : allClosed || (!!own?.confirmed && own.by === "human"),
      gateName: graph.nodes.find(n => n.id === sector.gateNodeId)?.name ?? "Nenastavena", blockedBy: [] };
  }
  for (const sector of graph.nodes.filter(n => n.kind === "sector")) {
    const scope = new Set<string>([sector.id]);
    let parent = sector.parentId;
    while (parent && !scope.has(parent)) { scope.add(parent); parent = graph.nodes.find(n => n.id === parent)?.parentId ?? null; }
    result[sector.id].blockedBy = [...new Set(graph.edges.filter(e => (e.port ?? "next") === "next" && scope.has(e.target) && graph.nodes.find(n => n.id === e.target)?.kind === "sector")
      .flatMap(e => {
        const source = graph.nodes.find(n => n.id === e.source);
        if (!source) return [];
        const blocked = source.kind === "sector" ? !result[source.id]?.verified : !state.nodes[source.id]?.done?.confirmed;
        return blocked ? [source.name] : [];
      }))];
  }
  return result;
}
