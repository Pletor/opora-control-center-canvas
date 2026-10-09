import { expect, it } from "vitest";
import { compactCheckCount } from "./compact-indicators";

it("počítá unikátní úspěšné kontroly, omezuje počet a zachová selhání", () => {
  const runs = [{ checkId: "a", exitCode: 0 }, { checkId: "a", exitCode: 0 }, { checkId: "b", exitCode: 1 }];
  expect(compactCheckCount({ checks: [{}] } as never, { checksRun: runs } as never)).toEqual({ total: 1, finished: 1, failed: 1 });
  expect(compactCheckCount({} as never)).toEqual({ total: 0, finished: 0, failed: 0 });
});
