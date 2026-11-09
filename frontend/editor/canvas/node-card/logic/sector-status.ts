import type { Graph, CanvasNode } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { BoardIndex } from "@/editor/canvas/board/logic/board-index";

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

/** Počty karet a stav ověření pro každý sektor. S indexem plátna (`BoardIndex`) jedním průchodem předků
 *  místo průchodu všemi uzly pro každý sektor; výsledek je stejný jako bez něj. */
export function sectorViews(graph: Graph, state: DesktopState, index?: BoardIndex) {
  const result: Record<string, { closed: number; total: number; verified: boolean; gateName: string; blockedBy: string[] }> = {};
  const nodeOf = (id: string | null | undefined) => index ? (id ? index.byId.get(id) : undefined) : graph.nodes.find(n => n.id === id);
  const sectors = graph.nodes.filter(n => n.kind === "sector");
  const membersBySector = index ? sectorMembers(graph, sectors, index) : null;
  for (const sector of sectors) {
    const members = membersBySector?.get(sector.id) ?? (membersBySector ? [] : graph.nodes.filter(n => {
      if (n.kind !== "node") return false;
      let cursor = n.parentId;
      const seen = new Set<string>();
      while (cursor && !seen.has(cursor)) {
        if (cursor === sector.id) return true;
        seen.add(cursor); cursor = graph.nodes.find(p => p.id === cursor)?.parentId ?? null;
      }
      return false;
    }));
    const closed = members.filter(n => state.nodes[n.id]?.done?.confirmed).length;
    const gate = sector.gateNodeId ? state.nodes[sector.gateNodeId]?.done : undefined;
    const gateNode = nodeOf(sector.gateNodeId);
    const scenario = gateNode?.scenario;
    const run = sector.gateNodeId ? state.nodes[sector.gateNodeId]?.scenarioRun : undefined;
    const scenarioReady = !scenario || (run?.command === scenario.command && run?.failed === 0);
    const own = state.nodes[sector.id]?.done;
    const allClosed = members.length > 0 && closed === members.length;
    result[sector.id] = { closed, total: members.length,
      verified: sector.gateNodeId ? !!gate?.confirmed && gate.by === "human" && allClosed && scenarioReady
        : allClosed || (!!own?.confirmed && own.by === "human"),
      gateName: gateNode?.name ?? "Nenastavena", blockedBy: [] };
  }
  // Vazby `next` mířící do sektoru: bez indexu se filtrují znovu pro každý sektor, s indexem jednou.
  const intoSector = (e: Graph["edges"][number]) => !e.relation && (e.port ?? "next") === "next" && nodeOf(e.target)?.kind === "sector";
  const sectorEdges = index ? graph.edges.filter(intoSector) : null;
  for (const sector of sectors) {
    const scope = new Set<string>([sector.id]);
    let parent = sector.parentId;
    while (parent && !scope.has(parent)) { scope.add(parent); parent = nodeOf(parent)?.parentId ?? null; }
    const edges = sectorEdges ? sectorEdges.filter(e => scope.has(e.target)) : graph.edges.filter(e => scope.has(e.target) && intoSector(e));
    result[sector.id].blockedBy = [...new Set(edges.flatMap(e => {
      const source = nodeOf(e.source);
      if (!source) return [];
      const blocked = source.kind === "sector" ? !result[source.id]?.verified : !state.nodes[source.id]?.done?.confirmed;
      return blocked ? [source.name] : [];
    }))];
  }
  return result;
}

/** Karty (`node`) pod každým sektorem: jeden průchod předků od každé karty, s ochranou proti cyklu. */
function sectorMembers(graph: Graph, sectors: CanvasNode[], index: BoardIndex) {
  const members = new Map<string, CanvasNode[]>(sectors.map(s => [s.id, []]));
  for (const n of graph.nodes) {
    if (n.kind !== "node") continue;
    let cursor = n.parentId;
    const seen = new Set<string>();
    while (cursor && !seen.has(cursor)) {
      members.get(cursor)?.push(n);
      seen.add(cursor); cursor = index.byId.get(cursor)?.parentId ?? null;
    }
  }
  return members;
}
