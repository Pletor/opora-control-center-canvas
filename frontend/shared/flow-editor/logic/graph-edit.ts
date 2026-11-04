// Úpravy grafu verze jako čisté funkce: každá vrací nový graf, původní (neměnná verze) zůstává. Rodič z výsledku
// udělá draft; editor sám nic neukládá.
import { compatiblePort, edgeFor } from "./connection-policy";
import { specOf, type EdgeVia, type FlowGraph, type FlowNode, type FlowNodeDetail, type NodeTypes, type Point, type PortRef, type PortSpec } from "./flow-types";

/** Stálé čitelné id nového uzlu z posledního článku typu (`agent.claude` → `claude`, `claude-2`, …). */
export function nextNodeId(graph: FlowGraph, type: string): string {
  const base = (type.split(".").pop() || "uzel").replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
  let id = base;
  for (let n = 2; graph.nodes.some((node) => node.id === id); n += 1) id = `${base}-${n}`;
  return id;
}

/** `preset`: parametry varianty typu (např. režim vektorového úložiště), přepíšou prázdné výchozí. */
export function addNode(graph: FlowGraph, types: NodeTypes, type: string, position: Point, preset?: Record<string, unknown>): { graph: FlowGraph; node: FlowNode } {
  const spec = types.get(type);
  if (!spec) throw new Error(`Neznámý typ uzlu ${type}.`);
  const node: FlowNode = { id: nextNodeId(graph, type), type, type_version: spec.version, params: { ...seedParams(spec.params), ...preset }, position: { ...position } };
  return { graph: { ...graph, nodes: [...graph.nodes, node] }, node };
}

/** Parametry, které katalog typu popisuje, dostane nový uzel prázdné, aby je člověk v inspektoru jen vyplnil. */
const seedParams = (described?: Record<string, string> | null) => Object.fromEntries(Object.keys(described ?? {}).map((key) => [key, ""]));

/** Varianta typu, která má port kompatibilní s `source`: nejdřív výchozí porty, pak varianty z registru (`variants`). */
export function variantFor(spec: { ports: readonly PortSpec[]; variants?: { params: Record<string, unknown>; ports: PortSpec[] }[] }, source: Pick<PortSpec, "kind" | "direction">) {
  if (compatiblePort(spec, source)) return { params: undefined, ports: spec.ports };
  return spec.variants?.find((variant) => compatiblePort(variant, source));
}

/** Nový uzel z „+“ u portu: postaví se vedle (hlavní tok vpravo, sub-uzel pod agenta) a rovnou se připojí. Když sedí jen
 * varianta typu, uzel dostane její `params` a vlastní porty (`node:<id>` v registru) ještě před spočtením vazby. */
export function addConnected(graph: FlowGraph, types: NodeTypes, type: string, from: PortRef): FlowGraph {
  const anchor = graph.nodes.find((node) => node.id === from.nodeId);
  const spec = types.get(type), source = anchor && specOf(types, anchor)?.ports.find((p) => p.name === from.port && p.direction === from.direction);
  if (!anchor || !spec || !source) throw new Error("Port neexistuje.");
  const variant = variantFor(spec, source);
  const target = variant && compatiblePort(variant, source);
  if (!variant || !target) throw new Error(`Typ ${type} nemá port ${source.kind}.`);
  const at = anchor.position ?? { x: 0, y: 0 };
  const offset = source.kind === "main" ? { x: from.direction === "out" ? 260 : -260, y: 0 } : { x: 0, y: from.direction === "in" ? 200 : -200 };
  const added = addNode(graph, types, type, { x: at.x + offset.x, y: at.y + offset.y }, variant.params);
  const registry = variant.params ? new Map(types).set(`node:${added.node.id}`, { ...spec, ports: variant.ports }) : types;
  const edge = edgeFor(added.graph, registry, from, { nodeId: added.node.id, port: target.name, direction: target.direction });
  return { ...added.graph, edges: [...added.graph.edges, edge] };
}

export function connect(graph: FlowGraph, types: NodeTypes, a: PortRef, b: PortRef): FlowGraph {
  return { ...graph, edges: [...graph.edges, edgeFor(graph, types, a, b)] };
}

/** Uzel odejde i se svými vazbami a z rámců (rámec bez uzlů zmizí). */
export function removeNode(graph: FlowGraph, nodeId: string): FlowGraph {
  const groups = graph.groups?.map((group) => ({ ...group, nodeIds: group.nodeIds.filter((id) => id !== nodeId) })).filter((group) => group.nodeIds.length);
  return { ...graph, nodes: graph.nodes.filter((n) => n.id !== nodeId), edges: graph.edges.filter((e) => e.source_node !== nodeId && e.target_node !== nodeId),
    ...(groups ? { groups } : {}) };
}

export function removeEdge(graph: FlowGraph, edgeId: string): FlowGraph {
  return { ...graph, edges: graph.edges.filter((edge) => edge.id !== edgeId) };
}

/** Přechod hrany mezi vrstvami (`via`); `undefined` ho odebere. */
export function setEdgeVia(graph: FlowGraph, edgeId: string, via: EdgeVia | undefined): FlowGraph {
  return { ...graph, edges: graph.edges.map((edge) => {
    if (edge.id !== edgeId) return edge;
    const { via: _old, ...rest } = edge;
    return via ? { ...rest, via } : rest;
  }) };
}

export function moveNode(graph: FlowGraph, nodeId: string, position: Point): FlowGraph {
  const rounded = { x: Math.round(position.x), y: Math.round(position.y) };
  return { ...graph, nodes: graph.nodes.map((node) => node.id === nodeId ? { ...node, position: rounded } : node) };
}

/** Parametr uzlu; `undefined` parametr odebere. */
export function setParam(graph: FlowGraph, nodeId: string, key: string, value: unknown): FlowGraph {
  return { ...graph, nodes: graph.nodes.map((node) => {
    if (node.id !== nodeId) return node;
    const params = { ...(node.params ?? {}) };
    if (value === undefined) delete params[key]; else params[key] = value;
    return { ...node, params };
  }) };
}

/** Pole uzlu plátna toku (`notes`, `inputSchema`, `onError` …); `undefined` pole odebere. */
export function setNodeField<K extends keyof FlowNodeDetail>(graph: FlowGraph, nodeId: string, key: K, value: FlowNodeDetail[K] | undefined): FlowGraph {
  return { ...graph, nodes: graph.nodes.map((node) => {
    if (node.id !== nodeId) return node;
    const next = { ...node };
    if (value === undefined) delete next[key]; else Object.assign(next, { [key]: value });
    return next;
  }) };
}
