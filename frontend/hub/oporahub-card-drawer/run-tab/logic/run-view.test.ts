import { describe, expect, it } from "vitest";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import type { BudgetContext } from "@/hub/execution-budgets/logic/execution-budgets";
import { budgetMeters, clock, latestExecution, leaseView, selfCheckChips } from "./run-view";

const execution = (extra: Partial<ExecutionSummary> = {}): ExecutionSummary => ({
  executionId: "ex1", project: "p", workspace: "w", nodeId: "c1", epoch: 3, acceptedRevision: "r", assignmentDigest: "d".repeat(64),
  expiresAt: 1300, serverNow: 1000, state: "running", createdAt: "2026-10-22T10:00:00Z", ...extra });

describe("run view", () => {
  it("formats clocks", () => {
    expect(clock(252)).toBe("04:12");
    expect(clock(3725)).toBe("1:02:05");
    expect(clock(-5)).toBe("00:00");
  });
  it("picks the running execution, else the newest", () => {
    const old = execution({ executionId: "a", state: "reported", createdAt: "2026-10-21" });
    const fresh = execution({ executionId: "b", state: "released", createdAt: "2026-10-22" });
    expect(latestExecution([old, fresh], "c1")?.executionId).toBe("b");
    expect(latestExecution([old, execution({ executionId: "r" }), fresh], "c1")?.executionId).toBe("r");
    expect(latestExecution([old], "other")).toBeNull();
  });
  it("counts the lease down from server time, not the browser clock", () => {
    const view = leaseView(execution(), 50_000, 49_948);
    expect(view).toMatchObject({ state: "active", remaining: 248, label: "04:08" });
    expect(leaseView(execution(), 60_000, 49_948).state).toBe("expired");
    expect(leaseView(execution({ state: "reported" }), 0, 0).state).toBe("closed");
    expect(leaseView(null, 0, 0).state).toBe("none");
  });
  it("builds budget meters with honest unknowns", () => {
    const budget = { attemptsUsed: 1, repairRoundsUsed: 1, policy: { limits: { maxAttempts: 3, maxRepairRounds: 1, maxRunSeconds: 600 } } } as unknown as BudgetContext;
    const run = execution({ budget: { maxRunSeconds: 600, admittedAt: 700 } as ExecutionSummary["budget"] });
    const meters = budgetMeters(budget, run, 1000);
    expect(meters.map(item => [item.key, item.text, item.tone])).toEqual([["attempts", "1 / 3", "ok"], ["repairs", "1 / 1", "bad"], ["time", "5 / 10 min", "ok"]]);
    expect(budgetMeters(null, null, null).every(item => item.tone === "gap")).toBe(true);
  });
  it("lists self-check chips from the gate", () => {
    expect(selfCheckChips({ status: "failed", source: null, missing: ["lint"], failed: ["test"], invalid: 0 }, { build: "required", test: "required" }))
      .toEqual([{ name: "build", state: "ok" }, { name: "lint", state: "missing" }, { name: "test", state: "failed" }]);
    expect(selfCheckChips(undefined, undefined)).toEqual([]);
  });
});
