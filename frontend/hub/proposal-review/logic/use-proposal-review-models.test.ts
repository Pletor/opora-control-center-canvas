import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { GraphProposal } from "@/hub/graph-proposals/logic/graph-proposals";
import { reviewReady, type ReviewTarget } from "./proposal-review";
import { reviewContext, reviewModel, reviewScope } from "./review-fixtures";
import { useProposalReview } from "./use-proposal-review";
import { useProposalReviewModels } from "./use-proposal-review-models";

vi.mock("./use-proposal-review", () => ({ useProposalReview: vi.fn() }));
vi.mock("./use-acceptance-policy", () => ({ useAcceptancePolicy: () => ({ refresh: vi.fn() }) }));

describe("selected graph review identity", () => {
  it.each([1, 2, 3, 4] as const)("loads the native review and enables matching acceptance for V%i", schemaVersion => {
    const target: ReviewTarget = { proposalId: "a".repeat(40), proposalKind: schemaVersion === 1 ? "graph-addition" : "graph-change" };
    const context = reviewContext(target);
    const requests: ReviewTarget[] = [];
    vi.mocked(useProposalReview).mockImplementation((_scope, requested) => {
      requests.push(requested);
      // Native server rejects a discriminator that does not match this stored record.
      const matches = requested.proposalId === target.proposalId && requested.proposalKind === target.proposalKind;
      return reviewModel({ target: requested, context: matches ? context : null, error: matches ? "" : "Wrong native proposal kind" });
    });
    let ready = false;
    function Probe() {
      const models = useProposalReviewModels(reviewScope, true, 1, {
        graph: { id: target.proposalId, schemaVersion, kind: schemaVersion === 1 ? "graph-additions" : "graph-changes" } as GraphProposal,
      });
      ready = reviewReady(models.graph, target, context.acceptedHead);
      return null;
    }
    renderToStaticMarkup(createElement(Probe));
    expect(requests[1]).toEqual(target);
    expect(ready).toBe(true);
    expect(reviewReady(reviewModel({ context }), target, "different-head")).toBe(false);
    expect(reviewReady(reviewModel({ context: { ...context, eligible: false } }), target, context.acceptedHead)).toBe(false);
  });
});
