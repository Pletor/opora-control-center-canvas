import { describe, expect, it } from "vitest";
import type { PlanStep } from "../../spec-tab/logic/spec-diff";
import { collectStepResults, stepColumns, stepDepths, stepProgress, stepRows, withBackendSteps } from "./step-status";

const step = (id: string, order: number, dependsOn: string[] = [], acceptance = ["a", "b"]): PlanStep =>
  ({ id, order, title: id, acceptance, dependsOn, kind: "code", files: [] });
const steps = [step("s1", 1), step("s2", 2, ["s1"]), step("s3", 3, ["s2"]), step("s4", 4, ["s2"]), step("s5", 5, ["s3", "s4"])];
const receipt = (createdAt: string, stepResults: unknown[]) => ({ executionId: "ex1", createdAt, result: { summary: "", stepResults } });

describe("step status", () => {
  it("keeps the newest report per step and ignores malformed items", () => {
    const results = collectStepResults([
      receipt("2026-10-22T10:05:00Z", [{ stepId: "s2", status: "done", evidence: { notes: "fixed", checks: ["pytest"] } }]),
      receipt("2026-10-22T10:00:00Z", [{ stepId: "s1", status: "done", evidence: { notes: "n" } }, { stepId: "s2", status: "failed", evidence: { notes: "x" } }, { stepId: 1 }]),
      { executionId: "ex0", createdAt: "x", result: { summary: "" } },
    ]);
    expect([...results.keys()].sort()).toEqual(["s1", "s2"]);
    expect(results.get("s2")).toMatchObject({ status: "done", evidence: { checks: ["pytest"], commits: [] } });
  });
  it("computes DAG depth by the longest dependency path", () => {
    expect(Object.fromEntries(stepDepths(steps))).toEqual({ s1: 0, s2: 1, s3: 2, s4: 2, s5: 3 });
    expect(Object.fromEntries(stepDepths([step("a", 1, ["b"]), step("b", 2, ["a"])]))).toEqual({ a: 1, b: 0 });
  });
  it("marks done steps, the current step and what still blocks later ones", () => {
    const results = collectStepResults([receipt("t1", [{ stepId: "s1", status: "done", evidence: { notes: "" } }, { stepId: "s2", status: "done", evidence: { notes: "" } }])]);
    const rows = stepRows(steps, results);
    expect(rows.map(row => row.status)).toEqual(["done", "done", "current", "waiting", "waiting"]);
    expect(rows[0].acceptanceMet).toBe(2);
    expect(rows[4].blockedBy).toEqual(["s3", "s4"]);
    expect(stepProgress(rows)).toMatchObject({ total: 5, done: 2, current: { id: "s3" } });
    expect(stepColumns(rows).map(column => column.map(row => row.id))).toEqual([["s1"], ["s2"], ["s3", "s4"], ["s5"]]);
  });
  it("honours the current step from agent-state and keeps failures visible", () => {
    const results = collectStepResults([receipt("t1", [{ stepId: "s1", status: "failed", evidence: { notes: "" } }])]);
    const rows = stepRows(steps, results, "s1");
    expect(rows[0]).toMatchObject({ status: "failed", isCurrent: true });
    expect(stepRows(steps, new Map(), "s4").find(row => row.isCurrent)?.id).toBe("s4");
  });
});

describe("backend step progress", () => {
  it("prefers agent-state step items over the newest run and keeps matching evidence", () => {
    const local = collectStepResults([receipt("t2", [{ stepId: "s1", status: "failed", evidence: { notes: "retry" } }, { stepId: "s2", status: "done", evidence: { notes: "n2" } }])]);
    const merged = withBackendSteps(local, [{ id: "s1", status: "done", executionId: "ex0" }, { id: "s2", status: "done", executionId: "ex1" },
      { id: "s3", status: "current", executionId: null }]);
    expect(merged.get("s1")).toMatchObject({ status: "done", executionId: "ex0", evidence: { notes: "" } });
    expect(merged.get("s2")?.evidence.notes).toBe("n2");
    expect(merged.has("s3")).toBe(false);
    expect(stepRows(steps, merged).map(row => row.status)).toEqual(["done", "done", "current", "waiting", "waiting"]);
    expect(withBackendSteps(local, [])).toBe(local);
  });
});
