import { expect, it } from "vitest";
import { addedIds } from "./use-added-pulse";

it("highlights additions, not reorder, existing entries or removal", () => {
  expect(addedIds(["a", "b"], ["b", "a", "c"])).toEqual(["c"]);
  expect(addedIds(["a", "b"], ["b"])).toEqual([]);
});

it("handles large lists in linear time and keeps duplicates of new ids", () => {
  const before = Array.from({ length: 20000 }, (_, i) => `n${i}`);
  const after = [...before, "x"];
  const started = performance.now();
  expect(addedIds(before, after)).toEqual(["x"]);
  expect(performance.now() - started).toBeLessThan(200);
});
