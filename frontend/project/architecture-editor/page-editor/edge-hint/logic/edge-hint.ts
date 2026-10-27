// Text popisku vazby na mapě Editoru stránky: druh toku česky a „zdroj → cíl“. Čistá funkce, žádný React.
import type { Graph, GraphEdge } from "@/shared/types/logic/types";
import { CARRIES_LABEL, canCarry } from "@/shared/edge-carries/logic/edge-carries";

export type EdgeHintText = { kind: string; route: string };

/** Řádek „druh toku“ a řádek „zdroj → cíl“; chybějící uzel se ukáže jeho ID, ať popisek nikdy nezmizí. */
export function edgeHintText(edge: GraphEdge, graph: Graph): EdgeHintText {
  const name = (id: string) => graph.nodes.find((node) => node.id === id)?.name.trim() || id;
  const kind = !canCarry(edge) ? "Druh toku se u této vazby nenastavuje"
    : edge.carries ? CARRIES_LABEL[edge.carries]
    : "Neurčeno – nastavte v Detailu prvku → Vazby";
  return { kind, route: `${name(edge.source)} → ${name(edge.target)}` };
}
