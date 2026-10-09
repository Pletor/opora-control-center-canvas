import { expect, it } from "vitest";
import { addedIds } from "./use-added-pulse";

it("highlights additions, not reorder, existing entries or removal", () => {
  expect(addedIds(["a", "b"], ["b", "a", "c"])).toEqual(["c"]);
  expect(addedIds(["a", "b"], ["b"])).toEqual([]);
});
