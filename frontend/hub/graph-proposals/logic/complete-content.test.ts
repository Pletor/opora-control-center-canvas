import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import GraphProposalContent from "../components/GraphProposalContent";
import GraphChangeReview from "../components/GraphChangeReview";
import type { GraphProposal } from "./graph-proposals";
import { graphActionPayload } from "./graph-proposals";

const proposal = {
  id: "complete", schemaVersion: 3, accepted: false, parentRevision: "parent", graphDigest: "digest",
  stateEffects: { revision: 4, before: { nodes: {}, rules: [] } },
  changes: { nodes: [], edges: [] }, resultGraph: { nodes: [{ id: "n", name: "Saved card" }], edges: [] },
  contentEffects: { documents: [{ nodeId: "n", kind: "text", expectedRevision: 2, before: "Previous text", value: "<script>proposed</script>" }],
    after: { rules: [], nodes: { n: { phase: "discover", criteria: [], steps: [],
      fragmentRefs: [{ fragmentId: "source", revision: 8 }], blocks: [{ id: "b", number: "1", title: "Proof block", text: "Stored instructions",
        state: { condition: "Review" }, ports: [{ id: "ready", label: "Ready port" }] }] } } } },
} as unknown as GraphProposal;

it("shows only persisted proposed content, expected revisions and pinned sources as escaped text", () => {
  const html = renderToStaticMarkup(createElement(GraphProposalContent, { proposal }));
  for (const text of ["Saved card", "Proof block", "Ready port", "Stored instructions", "revize 2", "revize 8", "Previous text", "čeká na přijetí"])
    expect(html).toContain(text);
  expect(html).toContain("&lt;script&gt;");
  expect(html).not.toContain("<script>");
  expect(html).not.toContain("<button");
  expect(html).not.toContain("<textarea");
});

it("requires and displays explicit baseline content adoption on first V3 acceptance", () => {
  const context = { acceptedHead: "parent", graphDigest: "digest", readOnly: false } as never;
  expect(() => graphActionPayload("p", "w", context, proposal, "accept", proposal.id)).toThrow("výchozí obsah");
  const complete = { ...proposal, baseGraph: { nodes: [], edges: [] }, changes: { nodes: [], edges: [], areaMembership: [] },
    stateEffects: { ...proposal.stateEffects, effects: {} },
    contentBase: { requiresAdoption: true, digest: "reviewed-base", entries: [{ kind: "text", target: "old", field: "text", value: "Prior working instruction", revision: 2 }] } } as unknown as GraphProposal;
  expect(graphActionPayload("p", "w", context, complete, "accept", complete.id)).toHaveProperty("adoptBaseContentDigest", "reviewed-base");
  const html = renderToStaticMarkup(createElement(GraphChangeReview, { proposal: complete }));
  expect(html).toContain("Výslovné převzetí výchozího obsahu");
  expect(html).toContain("Prior working instruction");
});

it("keeps selection local and refuses acceptance without complete V3 content", () => {
  const html = renderToStaticMarkup(createElement(GraphProposalContent, { proposal, nodeId: "other" }));
  expect(html).not.toContain("Stored instructions");
  expect(() => graphActionPayload("p", "w", { acceptedHead: "parent", graphDigest: "digest", readOnly: false } as never,
    { ...proposal, contentEffects: undefined }, "accept", proposal.id)).toThrow("obsah");
});
