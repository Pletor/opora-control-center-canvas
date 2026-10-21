import { describe, expect, it } from "vitest";
import { acceptedPlan, nextExecutionStep, observedExecutionLabel, pendingDecisions } from "./overview";
import type { GraphContext, GraphSummary } from "@/hub/graph-proposals/logic/graph-proposals";
import type { PlanContext, PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";

const node = { id: "n", name: "Karta", kind: "node" as const, parentId: null, purpose: "Cíl", x: 0, y: 0 };
const graph: GraphContext = { acceptedHead: "head", graphDigest: "digest", graphManifestId: "manifest", readOnly: false,
  requiresBaseAdoption: false, adoptionDocuments: [], acceptedGraph: { nodes: [node], edges: [] }, workingGraph: { nodes: [{ ...node }], edges: [] } };
const plan: PlanContext = { acceptedHead: "head", graphDigest: "digest", specificationsVersion: "spec", documents: [], acceptedDocuments: [], workingDiffers: false, readOnly: false };
const proposal = (id: string, extra: Partial<GraphSummary> = {}): GraphSummary => ({ id, parentRevision: "head", subject: id,
  by: { kind: "agent", name: "Uložený autor" }, createdAt: "2026-10-21T10:00:00Z", supersedes: null, requiresBaseAdoption: false, accepted: false, nodeCount: 1, edgeCount: 0, ...extra });
const execution: ExecutionSummary = { executionId: "e", project: "p", workspace: "w", nodeId: "n", epoch: 1,
  acceptedRevision: "head", assignmentDigest: "d", state: "running", serverNow: 100, expiresAt: 110 };
describe("overview preserves evidence boundaries", () => {
  it("does not turn a missing source into a matching plan", () => {
    expect(acceptedPlan(null, plan)).toMatchObject({ head: null, differs: null });
    expect(acceptedPlan(graph, null).warning).toContain("načten");
  });
  it("rejects mixed accepted heads", () => {
    expect(acceptedPlan(graph, { ...plan, acceptedHead: "other" })).toMatchObject({ head: null, differs: null });
  });
  it("detects structural and working specification drift", () => {
    expect(acceptedPlan(graph, plan).differs).toBe(false);
    expect(acceptedPlan({ ...graph, workingGraph: { nodes: [{ ...node, name: "Změna" }], edges: [] } }, plan).differs).toBe(true);
    expect(acceptedPlan(graph, { ...plan, workingDiffers: true }).differs).toBe(true);
  });
  it("leaves graph comparison unknown when snapshots are unavailable", () => {
    expect(acceptedPlan({ ...graph, acceptedGraph: undefined }, plan).differs).toBeNull();
  });
  it("flags legacy specification acceptance that has no accepted graph", () => {
    expect(acceptedPlan({ ...graph, graphManifestId: null, requiresBaseAdoption: true }, plan).warning).toContain("graf čeká");
  });
  it("does not offer accepted or known superseded graph proposals as new decisions", () => {
    const decisions = pendingDecisions([proposal("old"), proposal("replacement", { supersedes: "old" }), proposal("accepted", { accepted: true })], [], "head");
    expect(decisions.map(item => item.id)).toEqual(["replacement"]);
  });
  it("marks another parent stale and never invents graph impact", () => {
    expect(pendingDecisions([proposal("old", { parentRevision: "other" })], [], "head")[0]).toMatchObject({ stale: true, author: "Uložený autor", impact: "Změna grafu · přesný dopad zobrazí kontrola návrhu." });
  });
  it("does not infer stale proposals from missing or mixed accepted contexts", () => {
    const change: PlanChangeset = { id: "spec", parentRevision: "head", subject: "Spec", by: { kind: "human", name: "Člověk" }, createdAt: "2026-10-21T11:00:00Z", changes: [], accepted: false };
    for (const basis of [acceptedPlan(null, plan), acceptedPlan(graph, { ...plan, acceptedHead: "other" })]) {
      expect(basis.basisKnown).toBe(false);
      expect(pendingDecisions([proposal("loaded")], [change], basis.head, basis.basisKnown).map(item => item.stale)).toEqual([null, null]);
    }
  });
  it("distinguishes a confirmed initial null head from unavailable context", () => {
    const basis = acceptedPlan({ ...graph, acceptedHead: null }, { ...plan, acceptedHead: null });
    expect(basis.basisKnown).toBe(true);
    expect(pendingDecisions([proposal("initial", { parentRevision: null }), proposal("older", { parentRevision: "head" })], [], basis.head, basis.basisKnown).map(item => item.stale)).toEqual([false, true]);
  });
  it("keeps graph and specification decisions bound to their exact IDs", () => {
    const change: PlanChangeset = { id: "spec", parentRevision: "head", subject: "Spec", by: { kind: "human", name: "Člověk" }, createdAt: "2026-10-21T11:00:00Z", changes: [], accepted: false };
    expect(pendingDecisions([proposal("graph")], [change], "head").map(({ id, kind }) => [id, kind])).toEqual([["spec", "changes"], ["graph", "graph"]]);
  });
  it("revokes the local active marker at the deadline and changes the next step", () => {
    expect(observedExecutionLabel(execution, 9)).toContain("Aktivní");
    expect(observedExecutionLabel(execution, 10)).toContain("vypršelo");
    expect(nextExecutionStep(execution, 10)).toContain("nový claim");
  });
  it("does not call missing clock evidence active", () => {
    expect(observedExecutionLabel({ ...execution, serverNow: NaN })).toContain("nedoložena");
    expect(nextExecutionStep({ ...execution, expiresAt: NaN })).toContain("nový claim");
  });
  it("keeps reported distinct from independently verified and cancelled", () => {
    expect(observedExecutionLabel({ ...execution, state: "reported" })).toContain("neověřeno");
    expect(observedExecutionLabel({ ...execution, state: "cancelled" })).toContain("zrušeno");
  });
});
