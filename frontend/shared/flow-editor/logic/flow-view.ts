// Graf verze → uzly a hrany React Flow: tvar karty podle role, porty s polohou a počtem vazeb, stav běhu, značka
// rozdílu verzí a zvýraznění vybraného uzlu (třeba z logu). Handle má id `<směr>:<port>`, protože port `main` bývá
// na uzlu jako vstup i výstup.
import type { Edge, Node } from "@xyflow/react";
import { specOf, type FlowGraph, type FlowNode, type NodeTypes, type PortDirection, type PortRef } from "./flow-types";
import type { GraphDiff, NodeMark } from "./graph-diff";
import { nodeGlyph, nodeRole, portPlaces, typeLabel, type NodeRole, type PortPlace } from "./node-role";
import { edgeLabel, type NodeOverlay, type RunOverlay } from "./run-overlay";

export type PortView = PortPlace & { handleId: string; connected: number };
export type FlowCardData = {
  nodeId: string; family: string; name: string; glyph: string; role: NodeRole; ports: PortView[];
  run: NodeOverlay | null; mark: NodeMark | null; ghost: boolean; highlighted: boolean; issue: boolean; pinned: boolean; readOnly: boolean;
  /** Poznámka uzlu s `notesInFlow` jako podtitulek na kartě (n8n „Display note in flow“). */
  subtitle?: string;
};
export type FlowCardNode = Node<FlowCardData, "flow-card">;
/** `hidden`: uzly sbalených rámců, místo nich stojí na plátně jeden uzel rámce (`frame-view.ts`). */
export type ViewOptions = { overlay?: RunOverlay; diff?: GraphDiff | null; highlighted?: string | null; issues?: ReadonlySet<string>; readOnly?: boolean; hidden?: ReadonlySet<string> };

export const handleId = (direction: PortDirection, port: string) => `${direction}:${port}`;
export function parseHandle(nodeId: string, handle: string | null | undefined): PortRef | null {
  const [direction, ...rest] = (handle ?? "").split(":");
  return direction === "in" || direction === "out" ? { nodeId, direction, port: rest.join(":") } : null;
}

function card(node: FlowNode, graph: FlowGraph, types: NodeTypes, options: ViewOptions, ghost: boolean): FlowCardNode {
  const spec = specOf(types, node), { family, name } = typeLabel(node.type);
  const ports = portPlaces(spec).map((port): PortView => ({ ...port, handleId: handleId(port.direction, port.name),
    connected: graph.edges.filter((e) => port.direction === "out" ? e.source_node === node.id && e.source_port === port.name
      : e.target_node === node.id && e.target_port === port.name).length }));
  return {
    id: ghost ? `ghost:${node.id}` : node.id, type: "flow-card", position: node.position ?? { x: 0, y: 0 },
    draggable: !ghost && !options.readOnly, selectable: !ghost, connectable: !ghost && !options.readOnly,
    data: { nodeId: node.id, family, name, glyph: nodeGlyph(spec), role: nodeRole(spec), ports, run: ghost ? null : options.overlay?.get(node.id) ?? null,
      mark: options.diff?.nodes.get(node.id) ?? null, ghost, highlighted: options.highlighted === node.id, issue: options.issues?.has(node.id) ?? false,
      pinned: node.pinned_output !== undefined && node.pinned_output !== null, readOnly: ghost || !!options.readOnly,
      ...(node.notesInFlow && node.notes ? { subtitle: node.notes } : {}) },
  };
}

export function flowNodes(graph: FlowGraph, types: NodeTypes, options: ViewOptions = {}): FlowCardNode[] {
  const ghosts = options.diff?.ghosts ?? [];
  const shown = options.hidden?.size ? graph.nodes.filter((node) => !options.hidden!.has(node.id)) : graph.nodes;
  return [...shown.map((node) => card(node, graph, types, options, false)), ...ghosts.map((node) => card(node, graph, types, options, true))];
}

export function flowEdges(graph: FlowGraph, options: ViewOptions = {}): Edge[] {
  const overlay: RunOverlay = options.overlay ?? new Map();
  const added = new Set(options.diff?.addedEdges.map((edge) => edge.id));
  const live = graph.edges.map((edge): Edge => {
    const target = overlay.get(edge.target_node), label = edgeLabel(edge, overlay);
    const tone = added.has(edge.id) ? " flow-edge--added" : "";
    return { id: edge.id, source: edge.source_node, target: edge.target_node,
      sourceHandle: handleId("out", edge.source_port), targetHandle: handleId("in", edge.target_port),
      type: edge.kind === "main" ? "default" : "straight", label: label || edge.label || undefined,
      animated: target?.status === "running", className: `flow-edge flow-edge--${edge.kind === "main" ? "main" : "sub"}${tone}`,
      selectable: !options.readOnly };
  });
  const removed = (options.diff?.removedEdges ?? []).map((edge): Edge => {
    const ghost = (id: string) => graph.nodes.some((node) => node.id === id) ? id : `ghost:${id}`;
    return { id: `ghost:${edge.id}`, source: ghost(edge.source_node), target: ghost(edge.target_node),
      sourceHandle: handleId("out", edge.source_port), targetHandle: handleId("in", edge.target_port),
      className: "flow-edge flow-edge--removed", selectable: false };
  });
  return [...live, ...removed];
}
