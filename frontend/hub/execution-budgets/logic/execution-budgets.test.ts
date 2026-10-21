import { describe, expect, it } from "vitest";
import { BudgetIntent, BudgetRequests, budgetPayload, postBudget, type BudgetContext } from "./execution-budgets";
const context: BudgetContext = { project: "p", workspace: "w", nodeId: "n", acceptedHead: "accepted", policyHead: "policy", policy: null,
  canConfigure: true, canCancel: true, unavailableReason: null, enrolled: true, family: null, attemptsUsed: 2, repairRoundsUsed: 1,
  remainingAttempts: 1, remainingRepairRounds: 0, latestExecutionId: "e", blockedReason: null };
const limits = { maxRunSeconds: 900, maxAttempts: 3, maxRepairRounds: 1 };
describe("execution budget confirmation", () => {
  it("uses exact policy/accepted CAS and nested limits without caller-supplied consumption", () => {
    expect(budgetPayload(context, limits)).toEqual({ project: "p", workspace: "w", nodeId: "n", expectedPolicyHead: "policy", expectedAcceptedHead: "accepted", limits });
  });
  it("copies the confirmed limits so draft edits cannot mutate its snapshot", () => {
    const draft = { ...limits }; const snapshot = budgetPayload(context, draft); draft.maxAttempts = 10;
    expect(snapshot.limits.maxAttempts).toBe(3);
  });
  it.each([{ maxRunSeconds: 29 }, { maxRunSeconds: 86401 }, { maxAttempts: 0 }, { maxAttempts: 101 }, { maxRepairRounds: 3 }, { maxRepairRounds: -1 }, { maxAttempts: 1.5 }, { maxRunSeconds: NaN }])("rejects invalid limits %j", patch => {
    expect(() => budgetPayload(context, { ...limits, ...patch })).toThrow();
  });
  it("keeps archive cancellation permission separate from configuration", () => {
    expect(() => budgetPayload({ ...context, canConfigure: false, canCancel: true }, limits)).toThrow();
  });
  it("retains the same intent after an uncertain response but changes it for new CAS", () => {
    let number = 0; const intent = new BudgetIntent(() => `request-${++number}`);
    const payload = budgetPayload(context, limits);
    expect(intent.request(payload)).toBe(intent.request({ ...payload }));
    expect(intent.request({ ...payload, expectedPolicyHead: "next" })).toBe("request-2");
  });
  it("invalidates stale continuations and excludes concurrent mutations", () => {
    const requests = new BudgetRequests(); const valid = requests.begin()!;
    expect(requests.begin()).toBeNull(); requests.invalidate(); expect(valid()).toBe(false);
    requests.end(); expect(requests.begin()).not.toBeNull();
  });
  it("sends a mutation once when the network response is uncertain", async () => {
    const paths: string[] = [];
    const transport = (async (url: string) => { paths.push(url); if (paths.length === 1) return new Response("{}"); throw new Error("network"); }) as typeof fetch;
    await expect(postBudget("/api/oporahub/execution-budgets", {}, transport)).rejects.toThrow("network");
    expect(paths).toEqual(["/api/access/ui-session", "/api/oporahub/execution-budgets"]);
  });
});
