// Chyby kontroly grafu (`POST /api/flow/graph-check` → `{ok, errors}`) k místům na plátně. Server vrací věty; uzel
// a rámec se poznají podle začátku věty („Uzel <id>…“, „Skupina <id>: …“, „Hrana <id> vede na neexistující uzel 'x'“)
// a podle id, která v grafu opravdu jsou. Chyba uzlu patří i jeho rámci (sbalený rámec ji jinak schová). Co se přiřadit
// nedá, zůstane jen v pásu kontroly.
import type { FlowGraph } from "./flow-types";

export type CheckTargets = { nodes: ReadonlySet<string>; groups: ReadonlyMap<string, string[]> };

const NODE = /^Uzel (\S+?)[:\s]/, GROUP = /^Skupina (\S+?):/, PORT = /^Port (\S+?)\./, EDGE_NODE = /uzel (\S+?) nemá/;

export function checkTargets(errors: readonly string[], graph: FlowGraph): CheckTargets {
  const nodeIds = new Set(graph.nodes.map((node) => node.id)), groupIds = new Set((graph.groups ?? []).map((group) => group.id));
  const nodes = new Set<string>(), groups = new Map<string, string[]>();
  for (const error of errors) {
    const group = error.match(GROUP)?.[1];
    if (group && groupIds.has(group)) { groups.set(group, [...(groups.get(group) ?? []), error.slice(error.indexOf(":") + 1).trim()]); continue; }
    const node = error.match(NODE)?.[1] ?? error.match(PORT)?.[1] ?? error.match(EDGE_NODE)?.[1];
    if (!node || !nodeIds.has(node)) continue;
    nodes.add(node);
    const owner = graph.groups?.find((item) => item.nodeIds.includes(node));
    if (owner) groups.set(owner.id, [...(groups.get(owner.id) ?? []), error]);
  }
  return { nodes, groups };
}
