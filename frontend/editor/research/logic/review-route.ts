import type { ResearchScope } from "./research-types";

export function reviewRoute(search: string, scope: ResearchScope) {
  const params = new URLSearchParams(search);
  if (params.get("project") !== scope.project || params.get("workspace") !== scope.workspace) return null;
  const card = params.get("researchCard"), id = params.get("researchReview"), digest = params.get("researchDigest");
  return card && id && digest ? { card, id, digest } : null;
}
