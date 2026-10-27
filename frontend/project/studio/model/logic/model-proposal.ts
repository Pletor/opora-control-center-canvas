// Návrh počátečního modelu z architektury domény (docs/studio.md §4): jen návrh, nic se neukládá, člověk ho potvrdí.
// Každá karta OPORY pod doménou (stránka i komponenta, `kind: "node"`) dostane technickou komponentu s `binding.nodeId`,
// každá vazba s `carries` vazbu modelu s typem portu podle kontraktu. Typ komponenty se neodhaduje z názvu karty:
// vybere se nejmenší obecný typ katalogu, který má všechny potřebné porty. Vazbu, kterou pravidla modelu nedovolí
// (role Studia, chybějící port, duplicita) nebo která nemá `carries`, návrh nepřidá a vrátí ji v `unresolved` s důvodem.
import type { CanvasNode, EdgeCarries, Graph } from "@/shared/types/logic/types";
import { catalog } from "./catalog";
import { connectionError, createNode } from "./model-rules";
import { emptyStudioModel, type ComponentType, type PortType, type StudioModel, type StudioModelEdge } from "./model-types";

/** Převod `carries` → datový typ portu (docs/studio.md §4). */
export const CARRIES_PORT_TYPE: Record<EdgeCarries, PortType> = {
  navigation: "http-request", data: "data", command: "record-command", event: "event",
};

export type UnresolvedEdge = { edgeId: string; reason: string };
export type ModelProposal = { model: StudioModel; unresolved: UnresolvedEdge[] };

const COLUMNS = 4, STEP_X = 300, STEP_Y = 280;
/** Obecné typy bez poskytovatele cloudu; řízený Pod a Deployment se navrhovat nemají. */
const CANDIDATES = catalog.filter((type) => !type.provider && type.id !== "pod" && type.id !== "kubernetes-deployment");

function hasPorts(type: ComponentType, inputs: Set<PortType>, outputs: Set<PortType>): number {
  let missing = 0;
  for (const t of inputs) if (!type.ports.some((p) => p.direction === "input" && p.type === t)) missing++;
  for (const t of outputs) if (!type.ports.some((p) => p.direction === "output" && p.type === t)) missing++;
  return missing;
}

/** Typ s nejmenším počtem chybějících portů, pak s nejmenším počtem portů, pak podle pořadí katalogu. */
export function pickComponentType(inputs: Set<PortType>, outputs: Set<PortType>): ComponentType {
  return CANDIDATES.map((type, index) => ({ type, index, missing: hasPorts(type, inputs, outputs) }))
    .sort((a, b) => a.missing - b.missing || a.type.ports.length - b.type.ports.length || a.index - b.index)[0].type;
}

function domainNodes(graph: Graph, domainId: string): CanvasNode[] {
  const children = new Map<string, CanvasNode[]>();
  for (const node of graph.nodes) if (node.parentId) children.set(node.parentId, [...(children.get(node.parentId) ?? []), node]);
  const found: CanvasNode[] = [], seen = new Set<string>([domainId]), queue = [...(children.get(domainId) ?? [])];
  while (queue.length) {
    const node = queue.shift()!;
    if (seen.has(node.id)) continue;
    seen.add(node.id);
    if (node.kind === "node") found.push(node);
    queue.push(...(children.get(node.id) ?? []));
  }
  return found;
}

export const proposedNodeId = (oporaId: string) => "opora:" + oporaId;
export const proposedEdgeId = (oporaEdgeId: string) => "opora:" + oporaEdgeId;

export function proposeModelFromArchitecture(graph: Graph, domainId: string): ModelProposal {
  const cards = domainNodes(graph, domainId), inDomain = new Set(cards.map((card) => card.id));
  const edges = graph.edges.filter((edge) => inDomain.has(edge.source) && inDomain.has(edge.target));
  const inputs = new Map<string, Set<PortType>>(), outputs = new Map<string, Set<PortType>>(), unresolved: UnresolvedEdge[] = [];
  const add = (map: Map<string, Set<PortType>>, id: string, type: PortType) => map.set(id, (map.get(id) ?? new Set()).add(type));
  for (const edge of edges) if (edge.carries) { add(outputs, edge.source, CARRIES_PORT_TYPE[edge.carries]); add(inputs, edge.target, CARRIES_PORT_TYPE[edge.carries]); }
  const model = emptyStudioModel(domainId);
  cards.forEach((card, index) => {
    const type = pickComponentType(inputs.get(card.id) ?? new Set(), outputs.get(card.id) ?? new Set());
    const node = createNode(type.id, { x: (index % COLUMNS) * STEP_X, y: Math.floor(index / COLUMNS) * STEP_Y }, proposedNodeId(card.id));
    model.nodes.push({ ...node, name: (card.name || type.name).slice(0, 200), binding: { nodeId: card.id } });
  });
  for (const edge of edges) {
    if (!edge.carries) { unresolved.push({ edgeId: edge.id, reason: "Vazba neříká, co nese (carries)." }); continue; }
    const portType = CARRIES_PORT_TYPE[edge.carries];
    const fromNode = model.nodes.find((n) => n.binding?.nodeId === edge.source)!, toNode = model.nodes.find((n) => n.binding?.nodeId === edge.target)!;
    const out = catalog.find((t) => t.id === fromNode.type)!.ports.find((p) => p.direction === "output" && p.type === portType);
    const input = catalog.find((t) => t.id === toNode.type)!.ports.find((p) => p.direction === "input" && p.type === portType);
    if (!out || !input) { unresolved.push({ edgeId: edge.id, reason: `Typ komponenty nemá port ${portType}.` }); continue; }
    const from = { nodeId: fromNode.id, portId: out.id }, to = { nodeId: toNode.id, portId: input.id };
    const error = connectionError(model, from, to);
    if (error) { unresolved.push({ edgeId: edge.id, reason: error }); continue; }
    const modelEdge: StudioModelEdge = { id: proposedEdgeId(edge.id), from, to, type: portType, enabled: true, label: "", condition: "" };
    model.edges.push(modelEdge);
  }
  return { model, unresolved };
}
