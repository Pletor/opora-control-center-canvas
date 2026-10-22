import { describe, expect, it } from "vitest";
import { acceptanceLines, lineDiff, readSteps, specDiff, stepsDiff } from "./spec-diff";

const step = (id: string, order: number, extra: Record<string, unknown> = {}) => ({ id, order, title: id.toUpperCase(), acceptance: ["ok"], dependsOn: [], ...extra });

describe("spec diff", () => {
  it("normalises acceptance bullets and diffs lines in order", () => {
    expect(acceptanceLines("- a\n\n* b\n2) c\n  d  ")).toEqual(["a", "b", "c", "d"]);
    expect(lineDiff(["a", "b", "c"], ["a", "x", "c"])).toEqual([
      { kind: "same", text: "a" }, { kind: "removed", text: "b" }, { kind: "added", text: "x" }, { kind: "same", text: "c" }]);
    expect(lineDiff([], ["n"])).toEqual([{ kind: "added", text: "n" }]);
  });
  it("reads steps only when present and sorts them by order", () => {
    expect(readSteps({ goal: "", non_goals: "", acceptance: "" })).toBeNull();
    expect(readSteps({ goal: "", non_goals: "", acceptance: "", steps: [step("s2", 2), step("s1", 1), { bogus: true }] })?.map(item => item.id)).toEqual(["s1", "s2"]);
  });
  it("diffs steps per id with the changed fields", () => {
    const accepted = readSteps({ goal: "", non_goals: "", acceptance: "", steps: [step("s1", 1), step("s2", 2), step("s3", 3)] })!;
    const working = readSteps({ goal: "", non_goals: "", acceptance: "", steps: [step("s1", 1), step("s2", 2, { acceptance: ["ok", "new"] }), step("s4", 4, { dependsOn: ["s2"] })] })!;
    expect(stepsDiff(accepted, working).map(row => [row.id, row.kind, row.changed.join()])).toEqual([
      ["s1", "same", ""], ["s2", "changed", "acceptance"], ["s4", "added", ""], ["s3", "removed", ""]]);
  });
  it("counts every change and reports missing steps as null", () => {
    const view = specDiff({ goal: "G", non_goals: "N", acceptance: "a\nb" }, { goal: "G ", non_goals: "N2", acceptance: "a\nc" });
    expect(view.goal.state).toBe("same");
    expect(view.nonGoals.state).toBe("changed");
    expect(view.steps).toBeNull();
    expect(view.changes).toBe(3);
    const fresh = specDiff(null, { goal: "G", non_goals: "", acceptance: "", steps: [step("s1", 1)] });
    expect(fresh.steps?.[0].kind).toBe("added");
    expect(specDiff(null, null).changes).toBe(0);
  });
});
