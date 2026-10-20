import { describe, expect, it } from "vitest";
import { changesetPayload, inspectedFields, notifyCurrentPlanScope, type PlanContext, type PlanDocument } from "./plan-changes";
const fields = { goal: "Goal", non_goals: "", acceptance: "Works" };
const document: PlanDocument = { nodeId: "n", ownerWorkspace: "draft", revision: 3, fields };
const context: PlanContext = { acceptedHead: "accepted", graphDigest: "graph", specificationsVersion: "specs",
  documents: [document], acceptedDocuments: [document], workingDiffers: false, readOnly: false };

describe("isolated plan changes", () => {
  it("captures live preconditions and copies the draft without changing the working document", () => {
    const draft = { ...fields, goal: "New goal" };
    const payload = changesetPayload("p", "draft", " Reason ", context, document, draft);
    draft.goal = "Another edit";
    expect(payload).toEqual({ project: "p", workspace: "draft", subject: "Reason", parentRevision: "accepted",
      expectedGraphDigest: "graph", changes: [{ nodeId: "n", expectedRevision: 3, fields: { ...fields, goal: "New goal" } }] });
    expect(document.fields.goal).toBe("Goal");
  });
  it("refuses to propose without an accepted baseline or without a change", () => {
    expect(() => changesetPayload("p", "draft", "x", { ...context, acceptedHead: null }, document, fields)).toThrow();
    expect(() => changesetPayload("p", "draft", "x", context, document, { ...fields })).toThrow();
  });
  it("allows explicit reconciliation of working edits without changing them again", () => {
    const working = { ...document, revision: 4, fields: { ...fields, goal: "Working change" } };
    expect(changesetPayload("p", "draft", "Reconcile", context, working, working.fields).changes[0].fields.goal).toBe("Working change");
  });
  it("does not pretend a post-baseline card is already in the accepted plan", () => {
    expect(() => changesetPayload("p", "draft", "New", context, { ...document, nodeId: "new" }, { ...fields, goal: "Other" })).toThrow("Nová karta");
  });
  it("shows unaccepted working drift even when a proposal leaves that field untouched", () => {
    expect(inspectedFields({ nodeId: "n", ownerWorkspace: "draft", expectedRevision: 3,
      acceptedBefore: { ...document, fields: { ...fields, acceptance: "Old acceptance" } }, before: fields,
      fields: { ...fields, goal: "New goal" } })).toEqual(["goal", "acceptance"]);
  });
  it("shows a proposal that restores the accepted field over a changed working value", () => {
    expect(inspectedFields({ nodeId: "n", ownerWorkspace: "draft", expectedRevision: 3,
      acceptedBefore: document, before: { ...fields, goal: "Working" }, fields })).toEqual(["goal"]);
  });
});

describe("late accepted mutation invalidation", () => {
  it("refreshes the same scope after leaving the panel but cannot refresh another scope", async () => {
    const captured = { project: "p", workspace: "draft" };
    let current = { ...captured };
    let refreshes = 0;
    const complete = async () => {
      await Promise.resolve();
      notifyCurrentPlanScope(captured, current, () => refreshes++);
    };
    await complete(); // Panel mode is deliberately not part of the scope guard.
    expect(refreshes).toBe(1);
    const otherProject = complete();
    current = { project: "other", workspace: "draft" };
    await otherProject;
    const otherWorkspace = complete();
    current = { project: "p", workspace: "other" };
    await otherWorkspace;
    expect(refreshes).toBe(1);
  });
});
