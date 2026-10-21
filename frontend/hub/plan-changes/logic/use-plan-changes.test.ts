import { expect, it } from "vitest";
import { refreshedPlanSelection, selectedPlanDocument } from "./use-plan-changes";
import { changesetPayload, type PlanContext, type PlanDocument } from "./plan-changes";

const first: PlanDocument = { nodeId: "old-card", ownerWorkspace: "draft", revision: 1,
  fields: { goal: "Existing goal", non_goals: "", acceptance: "Checked" } };
const added: PlanDocument = { ...first, nodeId: "new-card", revision: 2 };
it("a newly observed process card absent from older plan context never silently targets the first card", () => {
  const selection = { key: "scope", node: added.nodeId, proposal: "old-proposal" };
  expect(selectedPlanDocument([first], selection, "scope")).toBeUndefined();
  const refreshed = refreshedPlanSelection(selection, "scope");
  expect(refreshed).toEqual({ key: "scope", node: added.nodeId, proposal: "" });
  expect(selectedPlanDocument([first], refreshed, "scope")).toBeUndefined();
  const context: PlanContext = { acceptedHead: "a".repeat(40), graphDigest: "g", specificationsVersion: "s",
    readOnly: false, workingDiffers: false, documents: [first, added], acceptedDocuments: [first, added] };
  const chosen = selectedPlanDocument(context.documents, refreshed, "scope")!;
  const payload = changesetPayload("draft", "draft", "Improve exact card", context, chosen, { ...chosen.fields, goal: "Improved goal" });
  expect(payload.changes.map(item => item.nodeId)).toEqual([added.nodeId]);
  expect(payload.changes[0].expectedRevision).toBe(added.revision);
});
it("only absent or other-scope selection uses the initial default", () => {
  expect(selectedPlanDocument([first], { key: "scope", node: "" }, "scope")).toBe(first);
  expect(selectedPlanDocument([first], { key: "other", node: "missing" }, "scope")).toBe(first);
  expect(selectedPlanDocument([], { key: "scope", node: "" }, "scope")).toBeUndefined();
});
