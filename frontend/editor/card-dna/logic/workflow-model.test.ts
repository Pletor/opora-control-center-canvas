import { expect, it } from "vitest";
import { compactCheckCount } from "./compact-indicators";
import { branchLabel, repairLoops, relatedNodes } from "./workflow-model";

it("odvozuje souhrn kontrol bez JSX", () => {
  const summary = compactCheckCount({ checks: [{ id: "one" }, { id: "two" }] } as never, {
    checksRun: [{ checkId: "one", exitCode: 0 }, { checkId: "one", exitCode: 0 }, { checkId: "two", exitCode: 1 }],
  } as never);
  expect(summary).toEqual({ total: 2, finished: 1, failed: 1 });
});

it("odvozuje workflow větev, opakování a sousední uzly bez Reactu", () => {
  expect(branchLabel({ state: { onMet: { kind: "branch", targetId: "next", note: "po opravě" } } } as never)).toBe("branch → next · po opravě");
  expect(repairLoops([{ id: "retry", retryOf: "original", status: "failed" }])).toEqual(["original → retry (failed)"]);
  expect(relatedNodes([{ source: "before", target: "current" }] as never, [{ id: "before", name: "Předchůdce" }] as never, "current", "before")).toEqual([{ id: "before", name: "Předchůdce" }]);
});
