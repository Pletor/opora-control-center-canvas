// Pravidla vazeb toku podle `kind` portu: stejná pravidla, jaká hlídá backend (`backend/flow/graph_check.py`), aby
// editor neplatnou vazbu vůbec nenabídl. Vazba vede z výstupu na vstup, oba porty mají stejný kind, port s
// `cardinality: "one"` nese jen jednu hranu a stejná vazba nevznikne dvakrát. Zobecněno ze Studia MODEL
// (`connectionError`), kde roli kindu hraje datový typ portu.
import type { FlowEdge, FlowGraph, NodeTypes, PortDirection, PortRef, PortSpec } from "./flow-types";

export function portOf(graph: FlowGraph, types: NodeTypes, ref: PortRef): PortSpec | undefined {
  const node = graph.nodes.find((item) => item.id === ref.nodeId);
  return node ? types.get(node.type)?.ports.find((port) => port.name === ref.port && port.direction === ref.direction) : undefined;
}

/** Jeden konec vazby pro obecnou kontrolu: uzel, port, směr a typ (kind) portu. `kind: null` = port neexistuje nebo
 * má jiný směr, než konec vazby žádá. Typ je text: toky mají `main`/`model`/…, Studio MODEL svých 12 datových typů. */
export type PortEnd = { nodeId: string; port: string; direction: PortDirection; kind: string | null; cardinality?: "one" | "many" };
export type PairRules = {
  /** Existuje už stejná vazba `from → to`? */
  exists: (from: PortEnd, to: PortEnd) => boolean;
  /** Kolik vazeb port už nese (jen pro porty s `cardinality: "one"`). */
  uses?: (end: PortEnd) => number;
  /** Pravidla navíc (role Studia) po shodě typů a před kontrolou duplicit. */
  extra?: (from: PortEnd, to: PortEnd) => string | null;
  missing?: string;
  self?: string;
};

/** Společná pravidla vazby `from → to` (výstup → vstup, stejný typ, bez duplicit, `cardinality: one`); null = platí.
 * Používá je editor toků i Studio MODEL, každý s vlastními hláškami a vlastním `extra`. */
export function pairError(from: PortEnd, to: PortEnd, rules: PairRules): string | null {
  if (from.nodeId === to.nodeId) return rules.self ?? "Uzel nelze propojit sám se sebou.";
  if (from.direction !== "out" || to.direction !== "in") return "Vazba musí vést z výstupu na vstup.";
  if (from.kind === null || to.kind === null) return rules.missing ?? "Port neexistuje.";
  if (from.kind !== to.kind) return `Nekompatibilní porty: ${from.kind} → ${to.kind}.`;
  const extra = rules.extra?.(from, to);
  if (extra) return extra;
  if (rules.exists(from, to)) return "Tato vazba již existuje.";
  if (rules.uses) for (const end of [from, to])
    if (end.cardinality === "one" && rules.uses(end)) return `Port ${end.nodeId}.${end.port} nese jen jednu vazbu.`;
  return null;
}

const uses = (edges: readonly FlowEdge[], ref: PortRef) => edges.filter((edge) => ref.direction === "out"
  ? edge.source_node === ref.nodeId && edge.source_port === ref.port
  : edge.target_node === ref.nodeId && edge.target_port === ref.port).length;

const endOf = (graph: FlowGraph, types: NodeTypes, ref: PortRef): PortEnd => {
  const spec = portOf(graph, types, ref);
  return { ...ref, kind: spec?.kind ?? null, cardinality: spec?.cardinality };
};

/** Proč vazba `from → to` neplatí; null = platí. Obrácený tah (ze vstupu na výstup) se nejdřív otočí. */
export function connectionError(graph: FlowGraph, types: NodeTypes, a: PortRef, b: PortRef): string | null {
  const [from, to] = a.direction === "in" && b.direction === "out" ? [b, a] : [a, b];
  return pairError(endOf(graph, types, from), endOf(graph, types, to), {
    exists: (f, t) => graph.edges.some((e) => e.source_node === f.nodeId && e.source_port === f.port && e.target_node === t.nodeId && e.target_port === t.port),
    uses: (end) => uses(graph.edges, end),
  });
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
