import { useProposalReview } from "./use-proposal-review";
import { useState } from "react";
import { useAcceptancePolicy } from "./use-acceptance-policy";
import type { ReviewScope } from "./proposal-review";

export function useProposalReviewModels(scope: ReviewScope, enabled: boolean, revision: number,
  selected: { spec?: { id: string } | null; graph?: { id: string; schemaVersion?: number } | null; content?: { id: string } | null }) {
  const [generation, setGeneration] = useState(0);
  const observed = JSON.stringify([revision, generation]), changed = () => setGeneration(value => value + 1);
  const policy = useAcceptancePolicy(scope, enabled, observed, changed);
  const spec = useProposalReview(scope, { proposalKind: "spec", proposalId: selected.spec?.id ?? "" }, enabled, observed, changed);
  const graph = useProposalReview(scope, { proposalKind: selected.graph?.schemaVersion === 2 ? "graph-change" : "graph-addition", proposalId: selected.graph?.id ?? "" }, enabled, observed, changed);
  const content = useProposalReview(scope, { proposalKind: "content", proposalId: selected.content?.id ?? "" }, enabled, observed, changed);
  return { policy, spec, graph, content, reset: () => { spec.reset(); graph.reset(); content.reset(); },
    refresh: () => { policy.refresh(); spec.refresh(); graph.refresh(); content.refresh(); } };
}
export type ProposalReviewModels = ReturnType<typeof useProposalReviewModels>;
