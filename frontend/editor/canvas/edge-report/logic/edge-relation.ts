import type { EdgeRelation, GraphEdge, InputRequirement } from "@/shared/types/logic/types";

export const RELATION_LABELS: Record<EdgeRelation, string> = {
  uses: "Používá", communicates_with: "Komunikuje s", requires: "Vyžaduje před zahájením", evidences: "Dokládá / zdůvodňuje",
};
export const MAX_RELATION_REASON = 1000;
export function withEdgeRelation(edge: GraphEdge, relation: EdgeRelation | "", reason: string, requirement: InputRequirement | undefined = edge.requirement): GraphEdge {
  const { relation: _relation, reason: _reason, requirement: _requirement, ...rest } = edge;
  return relation ? { ...rest, relation, ...(reason.trim() ? { reason: reason.trim() } : {}),
    ...(relation === "requires" && requirement ? { requirement } : {}) } : rest;
}
