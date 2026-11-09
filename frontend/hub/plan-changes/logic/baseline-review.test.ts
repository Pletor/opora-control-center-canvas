import { expect, it } from "vitest";
import { samePinnedDocuments } from "./baseline-review";

it("matches sorted native receipts, but rejects nested content and revision drift", () => {
  const live = [{ nodeId: "a", revision: 0, fields: { goal: "Exact", acceptance: "Check" } }];
  expect(samePinnedDocuments(live, [{ fields: { acceptance: "Check", goal: "Exact" }, revision: 0, nodeId: "a" }])).toBe(true);
  expect(samePinnedDocuments(live, [{ ...live[0], revision: 1 }])).toBe(false);
  expect(samePinnedDocuments(live, [{ ...live[0], fields: { goal: "Different", acceptance: "Check" } }])).toBe(false);
});
