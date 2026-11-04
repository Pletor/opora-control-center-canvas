// Porty podle parametrů (kontrakt knihovny §2 „ports(params)“). Registr posílá jen porty výchozích `params`
// a `dynamicPorts`; přesné porty uzlu spočte `POST /api/flow/node-ports`. Tady se skládá, na co se ptát:
// - uzel dynamického typu nebo s `onError: errorOutput` → porty pro jeho `params` (klíč dotazu = typ + params + onError);
// - varianty typu pro paletu: každá hodnota výčtového parametru z popisu registru („insert | load | retrieveAsTool“).
import type { FlowGraph, NodeTypeSpec } from "@/shared/flow-editor/logic/flow-types";

export type PortQuery = { key: string; type: string; params: Record<string, unknown>; onError?: string };

const stable = (value: unknown) => JSON.stringify(value, (_key, v) => v && typeof v === "object" && !Array.isArray(v)
  ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b))) : v);

/** Dotazy na porty uzlů grafu (uzel → dotaz); uzel statického typu bez chybového výstupu dotaz nepotřebuje. */
export function portQueries(graph: FlowGraph, types: ReadonlyMap<string, NodeTypeSpec>): Map<string, PortQuery> {
  const queries = new Map<string, PortQuery>();
  for (const node of graph.nodes) {
    const spec = types.get(node.type), onError = node.onError === "errorOutput" ? node.onError : undefined;
    if (!spec || (!spec.dynamicPorts && !onError)) continue;
    const params = node.params ?? {};
    queries.set(node.id, { key: stable([node.type, params, onError ?? null]), type: node.type, params, ...(onError ? { onError } : {}) });
  }
  return queries;
}

/** Výčtové hodnoty parametru z popisu registru: „a | b | c“ bez mezer v hodnotách; „true | false“ jako pravda/nepravda. */
export function enumValues(description: string): unknown[] {
  const parts = description.split("|").map((part) => part.trim());
  if (parts.length < 2 || parts.some((part) => !/^[A-Za-z][\w-]*$/.test(part))) return [];
  return parts.map((part) => part === "true" ? true : part === "false" ? false : part);
}

/** Sady `params` pro varianty dynamického typu: jeden výčtový parametr na sadu (ostatní výchozí). */
export function variantParams(spec: NodeTypeSpec): Record<string, unknown>[] {
  if (!spec.dynamicPorts) return [];
  return Object.entries(spec.params ?? {}).flatMap(([key, description]) => enumValues(description).map((value) => ({ [key]: value })));
}
