// Pravidla vazeb toku podle `kind` portu: stejná pravidla, jaká hlídá backend (`backend/flow/graph_check.py`), aby
// editor neplatnou vazbu vůbec nenabídl. Vazba vede z výstupu na vstup, oba porty mají stejný kind, port s
// `cardinality: "one"` nese jen jednu hranu a stejná vazba nevznikne dvakrát. Zobecněno ze Studia MODEL
// (`connectionError`), kde roli kindu hraje datový typ portu.
import type { FlowEdge, FlowGraph, NodeTypes, PortRef, PortSpec } from "./flow-types";

export function portOf(graph: FlowGraph, types: NodeTypes, ref: PortRef): PortSpec | undefined {
  const node = graph.nodes.find((item) => item.id === ref.nodeId);
  return node ? types.get(node.type)?.ports.find((port) => port.name === ref.port && port.direction === ref.direction) : undefined;
}

const uses = (edges: readonly FlowEdge[], ref: PortRef) => edges.filter((edge) => ref.direction === "out"
  ? edge.source_node === ref.nodeId && edge.source_port === ref.port
  : edge.target_node === ref.nodeId && edge.target_port === ref.port).length;

/** Proč vazba `from → to` neplatí; null = platí. Obrácený tah (ze vstupu na výstup) se nejdřív otočí. */
export function connectionError(graph: FlowGraph, types: NodeTypes, a: PortRef, b: PortRef): string | null {
  const [from, to] = a.direction === "in" && b.direction === "out" ? [b, a] : [a, b];
  if (from.nodeId === to.nodeId) return "Uzel nelze propojit sám se sebou.";
  if (from.direction !== "out" || to.direction !== "in") return "Vazba musí vést z výstupu na vstup.";
  const out = portOf(graph, types, from), input = portOf(graph, types, to);
  if (!out || !input) return "Port neexistuje.";
  if (out.kind !== input.kind) return `Nekompatibilní porty: ${out.kind} → ${input.kind}.`;
  if (graph.edges.some((e) => e.source_node === from.nodeId && e.source_port === from.port && e.target_node === to.nodeId && e.target_port === to.port))
    return "Tato vazba již existuje.";
  if (out.cardinality === "one" && uses(graph.edges, from)) return `Port ${from.nodeId}.${from.port} nese jen jednu vazbu.`;
  if (input.cardinality === "one" && uses(graph.edges, to)) return `Port ${to.nodeId}.${to.port} nese jen jednu vazbu.`;
  return null;
}

/** Vazba jako hrana grafu (kind z výstupního portu); neplatná vazba hodí chybu s důvodem. */
export function edgeFor(graph: FlowGraph, types: NodeTypes, a: PortRef, b: PortRef): FlowEdge {
  const error = connectionError(graph, types, a, b);
  if (error) throw new Error(error);
  const [from, to] = a.direction === "out" ? [a, b] : [b, a];
  const base = `${from.nodeId}-${to.nodeId}${to.port === "main" ? "" : "-" + to.port}`;
  let id = base;
  for (let n = 2; graph.edges.some((edge) => edge.id === id); n += 1) id = `${base}-${n}`;
  return { id, source_node: from.nodeId, source_port: from.port, target_node: to.nodeId, target_port: to.port, kind: portOf(graph, types, from)!.kind, label: "" };
}

/** Typy, které mají port opačného směru se stejným kindem: kandidáti pro „+“ u portu (paleta předfiltrovaná na port). */
export function compatiblePort(type: { ports: readonly PortSpec[] }, from: Pick<PortSpec, "kind" | "direction">): PortSpec | undefined {
  const want = from.direction === "out" ? "in" : "out";
  return type.ports.find((port) => port.kind === from.kind && port.direction === want);
}
