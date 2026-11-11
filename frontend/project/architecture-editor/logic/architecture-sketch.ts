// Export JSON náčrtu architektury: otevřený rozsah domény (stránka nebo doména) s potomky v téže doméně a vazby mezi nimi;
// bez domény všechny domény (aplikace) projektu. Bez Reactu, test vedle.
import type { Graph } from "@/shared/types/logic/types";
import { domainForNode } from "./domain-model";

export function architectureSketch(graph: Graph, domainId: string | null, scopeId: string | null): Graph {
  let ids: Set<string>;
  if (domainId) {
    ids = new Set([scopeId ?? domainId]);
    for (let added = true; added; ) {
      added = false;
      for (const node of graph.nodes) if (node.parentId && ids.has(node.parentId) && !ids.has(node.id)) { ids.add(node.id); added = true; }
    }
    ids = new Set([...ids].filter((id) => domainForNode(graph, id)?.id === domainId));
  } else ids = new Set(graph.nodes.filter((node) => node.site?.kind === "application").map((node) => node.id));
  return { nodes: graph.nodes.filter((node) => ids.has(node.id)), edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)) };
}
