import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import PlanChanges from "./PlanChanges";
import type { PlanChangesView } from "../logic/use-plan-changes";

it("missing explicit card explains refresh and exposes no other card editor or proposal submit", () => {
  const model = { busy: false, readOnly: false, context: { acceptedHead: "a".repeat(40), acceptedDocuments: [], documents: [] },
    documents: [], document: undefined, fields: undefined, missingDocument: "fresh-process-card", subject: "Improve card",
    error: "", notice: "", items: [], refresh: vi.fn() } as unknown as PlanChangesView;
  const html = renderToStaticMarkup(createElement(PlanChanges, { model }));
  expect(html).toContain("fresh-process-card"); expect(html).toContain("jiná karta se místo ní nevybere");
  expect(html).toContain("Obnovit a zahodit rozepsané změny");
  expect(html).not.toContain("Uložit návrh změny"); expect(html).not.toContain("<textarea");
});

it("shows complete Harness content before baseline and proposal acceptance", () => {
  const plain = { goal: "Goal", non_goals: "", acceptance: "Checks" };
  const fields = { ...plain, harness: { schema: "harness.kit/1", problems: ["typescript"], resources: [{
    slot: "rules.quality", resource: "rule:quality", category: "rules", digest: "a".repeat(64),
    content: "PINNED_REVIEW_CONTENT", requires: ["mcp:context7"] }] } };
  const document = { nodeId: "a", ownerWorkspace: "draft", revision: 1, fields };
  const model = { busy: false, readOnly: false, context: { acceptedHead: null, acceptedDocuments: [], documents: [document] },
    documents: [document], document: undefined, fields: undefined, subject: "Tools", name: () => "Card A",
    error: "", notice: "", items: [], refresh: vi.fn() } as unknown as PlanChangesView;
  const baseline = renderToStaticMarkup(createElement(PlanChanges, { model }));
  expect(baseline).toContain("PINNED_REVIEW_CONTENT"); expect(baseline).toContain("mcp:context7");
  model.context!.acceptedHead = "a".repeat(40);
  model.inspected = { id: "b".repeat(40), subject: "Tools", parentRevision: "a".repeat(40), accepted: false,
    by: { kind: "agent", name: "Builder" }, createdAt: "2026-10-23T00:00:00Z", changes: [{ nodeId: "a",
      ownerWorkspace: "draft", expectedRevision: 0, before: plain, acceptedBefore: { ...document, revision: 0, fields: plain }, fields }] };
  const proposal = renderToStaticMarkup(createElement(PlanChanges, { model }));
  expect(proposal).toContain("PINNED_REVIEW_CONTENT"); expect(proposal).toContain("data-oh-spec-field=\"harness\"");
});
