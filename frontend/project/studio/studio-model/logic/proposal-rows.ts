// Vazby architektury, které návrh modelu nepřevedl (`proposeModelFromArchitecture` → `unresolved`), jako řádky
// k ručnímu dořešení: odkud a kam vazba v OPOŘE vede (jména karet) a proč ji pravidla modelu nevzala. Bez Reactu.
import type { Graph } from "@/shared/types/logic/types";
import type { UnresolvedEdge } from "../../model/logic/model-proposal";

export type UnresolvedRow = { edgeId: string; from: string; to: string; reason: string };

export function unresolvedRows(graph: Graph, unresolved: readonly UnresolvedEdge[]): UnresolvedRow[] {
  const names = new Map(graph.nodes.map((node) => [node.id, node.name || node.id]));
  const edges = new Map(graph.edges.map((edge) => [edge.id, edge]));
  return unresolved.map(({ edgeId, reason }) => {
    const edge = edges.get(edgeId);
    return { edgeId, reason, from: edge ? names.get(edge.source) ?? edge.source : "?", to: edge ? names.get(edge.target) ?? edge.target : "?" };
  });
}

/** Počet s českým tvarem slova („1 vazba“, „3 vazby“, „5 vazeb“). */
export function counted(count: number, [one, few, many]: readonly [string, string, string]): string {
  return `${count} ${count === 1 ? one : count >= 2 && count <= 4 ? few : many}`;
}
