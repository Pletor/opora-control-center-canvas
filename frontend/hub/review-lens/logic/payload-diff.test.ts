import { describe, expect, it } from "vitest";
import { flatten, payloadDiff } from "./payload-diff";

describe("payload diff", () => {
  it("flattens JSON leaves to paths", () => {
    expect([...flatten({ a: { b: [1, { c: "x" }] }, e: {}, f: null })]).toEqual([["a.b[0]", "1"], ["a.b[1].c", '"x"'], ["e", "{}"], ["f", "null"]]);
    expect([...flatten(5)]).toEqual([["$", "5"]]);
  });
  it("marks added, changed, same and removed leaves", () => {
    expect(payloadDiff({ floor: "main", pr: 44, sha: "abc" }, { floor: "main", pr: 43, old: true })).toEqual([
      { path: "floor", status: "same", before: '"main"', after: '"main"' },
      { path: "pr", status: "changed", before: "43", after: "44" },
      { path: "sha", status: "added", after: '"abc"' },
      { path: "old", status: "removed", before: "true" },
    ]);
  });
  it("without a before sample every leaf is plain", () => {
    expect(payloadDiff({ a: 1 })).toEqual([{ path: "a", status: "same", after: "1" }]);
  });
});
