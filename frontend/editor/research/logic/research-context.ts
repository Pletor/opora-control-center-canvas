import { recordsInScope, type WorkScope } from "@/shared/work-scope/logic/work-scope";
import type { ResearchEdge, ResearchHeader } from "./research-types";
/** Deep links and inspector navigation pass through the same context boundary as the canvas. */
export function researchContext(cards: ResearchHeader[], edges: ResearchEdge[], scope: WorkScope,
  selected: { kind: "card" | "edge"; id: string } | null) {
  const scopedCards = recordsInScope(cards, scope);
  const ids = new Set(scopedCards.map(card => card.id));
  const scopedEdges = edges.filter(edge => ids.has(edge.fromId) && ids.has(edge.toId));
  return { scopedCards, scopedEdges,
    currentCard: scopedCards.find(card => selected?.kind === "card" && card.id === selected.id),
    currentEdge: scopedEdges.find(edge => selected?.kind === "edge" && edge.id === selected.id) };
}
