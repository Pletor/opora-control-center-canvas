// Čistý model sloupce „Hierarchický editor komponenty“: z grafu staví oblasti → sektory → uzly,
// stav uzlu, drobečky, workflow podle vazeb `next` a kroky pipeline. Oblasti seskupují sourozence
// geometricky (`areaOf`), nikdy přes `parentId`; nic se neukládá ani nevymýšlí.
import type { CanvasNode, CardLayer, Graph } from "@/shared/types/logic/types";
import { NODE_PHASES, type NodePhase } from "@/shared/desktop-state/logic/types";
import { areaOf, isArea } from "@/editor/canvas/area/logic/area-model";

export type NodeStatus = "done" | "active" | "waiting";
export const STATUS_LABEL: Record<NodeStatus, string> = { done: "Hotovo", active: "V řešení", waiting: "Čeká" };
export const PHASE_LABEL: Record<NodePhase, string> = {
  discover: "Průzkum",
  define: "Zadání",
  build: "Stavba",
  verify: "Ověření",
  live: "Provoz",
};

/** Barva dílku: vrstva karty, nebo `neutral`, když ji karta nemá. */
export type Tone = CardLayer | "neutral";
export type StructureItem = { id: string; name: string; purpose: string; kind: CanvasNode["kind"]; tone: Tone; status: NodeStatus };
export type StructureSector = { id: string; name: string; purpose: string; tone: Tone; items: StructureItem[] };
/** Oblast na plátně; `id: null` je implicitní skupina přímých dětí rootu mimo oblast (bez rámu). */
export type StructureGroup = { id: string | null; name: string; purpose: string; sectors: StructureSector[]; items: StructureItem[] };
export type PipelineStep = { phase: NodePhase; label: string; state: "past" | "current" | "future" };

/** Hotovo vyhrává; build a verify jsou rozpracované; vše ostatní čeká. */
export function nodeStatus(phase: NodePhase, done: boolean): NodeStatus {
  if (done) return "done";
  return phase === "build" || phase === "verify" ? "active" : "waiting";
}

export function toneOf(node: CanvasNode): Tone {
  return node.card?.layer ?? "neutral";
}

/** Sektor nemá vlastní vrstvu: bere nejčastější vrstvu svých uzlů, při shodě první v pořadí grafu. */
function sectorTone(items: StructureItem[]): Tone {
  const counts = new Map<Tone, number>();
  for (const item of items) if (item.tone !== "neutral") counts.set(item.tone, (counts.get(item.tone) ?? 0) + 1);
  let best: Tone = "neutral";
  let bestCount = 0;
  for (const [tone, count] of counts) if (count > bestCount) [best, bestCount] = [tone, count];
  return best;
}

const visible = (node: CanvasNode) => node.kind !== "comment" && !isArea(node);

export function buildStructure(
  graph: Graph,
  rootId: string,
  phaseOf: (id: string) => NodePhase,
  isDone: (id: string) => boolean,
): StructureGroup[] {
  const item = (node: CanvasNode): StructureItem => ({
    id: node.id,
    name: node.name,
    purpose: node.purpose,
    kind: node.kind,
    tone: toneOf(node),
    status: nodeStatus(phaseOf(node.id), isDone(node.id)),
  });
  const sector = (node: CanvasNode): StructureSector => {
    const items = graph.nodes.filter((child) => child.parentId === node.id && visible(child)).map(item);
    return { id: node.id, name: node.name, purpose: node.purpose, tone: sectorTone(items), items };
  };
  const children = graph.nodes.filter((node) => node.parentId === rootId);
  const loose: StructureGroup = { id: null, name: "", purpose: "", sectors: [], items: [] };
  const groups = new Map<string, StructureGroup>();
  for (const area of children.filter(isArea))
    groups.set(area.id, { id: area.id, name: area.name, purpose: area.purpose, sectors: [], items: [] });
  for (const child of children.filter(visible)) {
    const group = groups.get(areaOf(child, graph.nodes)?.id ?? "") ?? loose;
    if (child.kind === "sector") group.sectors.push(sector(child));
    else group.items.push(item(child));
  }
  const hasLoose = loose.sectors.length > 0 || loose.items.length > 0;
  return [...(hasLoose ? [loose] : []), ...groups.values()];
}

/** Cesta od nejvyššího předka po vybraný prvek; když vybraný neleží pod rootem, končí rootem. */
export function breadcrumbs(graph: Graph, rootId: string, selectedId: string | null): CanvasNode[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const chain = (from: string): CanvasNode[] => {
    const out: CanvasNode[] = [];
    const seen = new Set<string>();
    for (let cursor: string | null = from; cursor && !seen.has(cursor); ) {
      seen.add(cursor);
      const node = byId.get(cursor);
      if (!node) break;
      out.unshift(node);
      cursor = node.parentId;
    }
    return out;
  };
  const toSelected = selectedId ? chain(selectedId) : [];
  return toSelected.some((node) => node.id === rootId) ? toSelected : chain(rootId);
}

/** Všichni potomci rootu přes `parentId` (bez rootu), odolné vůči cyklu. */
export function descendantIds(graph: Graph, rootId: string): Set<string> {
  const out = new Set<string>();
  const queue = [rootId];
  while (queue.length) {
    const parent = queue.shift()!;
    for (const node of graph.nodes)
      if (node.parentId === parent && node.id !== rootId && !out.has(node.id)) {
        out.add(node.id);
        queue.push(node.id);
      }
  }
  return out;
}

/**
 * Řetěz workflow: potomci rootu spojení vazbou `next` (starší vazba bez portu je také `next`),
 * seřazení topologicky; při shodě rozhoduje pořadí v grafu. Uzly v cyklu se připojí na konec.
 */
export function workflowChain(graph: Graph, rootId: string): CanvasNode[] {
  const inside = descendantIds(graph, rootId);
  const edges = graph.edges.filter(
    (edge) => (edge.port ?? "next") === "next" && edge.source !== edge.target && inside.has(edge.source) && inside.has(edge.target),
  );
  const used = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const nodes = graph.nodes.filter((node) => used.has(node.id) && visible(node));
  const indegree = new Map(nodes.map((node) => [node.id, 0]));
  for (const edge of edges) indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
  const order: CanvasNode[] = [];
  const placed = new Set<string>();
  let ready = nodes.filter((node) => indegree.get(node.id) === 0);
  while (ready.length) {
    const [next, ...rest] = ready;
    order.push(next);
    placed.add(next.id);
    for (const edge of edges.filter((e) => e.source === next.id)) indegree.set(edge.target, indegree.get(edge.target)! - 1);
    const fresh = nodes.filter((node) => !placed.has(node.id) && indegree.get(node.id) === 0 && !rest.includes(node));
    ready = nodes.filter((node) => rest.includes(node) || fresh.includes(node));
  }
  return [...order, ...nodes.filter((node) => !placed.has(node.id))];
}

/** Kroky pipeline práce s vyznačenou fází prvku. */
export function pipelineSteps(current: NodePhase): PipelineStep[] {
  const at = NODE_PHASES.indexOf(current);
  return NODE_PHASES.map((phase, index) => ({
    phase,
    label: PHASE_LABEL[phase],
    state: index < at ? "past" : index === at ? "current" : "future",
  }));
}
