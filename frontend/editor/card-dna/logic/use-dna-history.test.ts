import { describe, expect, it } from "vitest";
import { advanceHistoryCursors, mergeHistoryItems } from "./use-dna-history";

describe("DNA history pagination", () => {
  it("merges one page from each real source and advances all cursors", () => {
    const cursors = advanceHistoryCursors(
      { results: 40, incoming: "90", outgoing: "80" },
      { results: { nextBefore: 20 }, incoming: { nextBefore: 60 }, outgoing: { nextBefore: null } },
    );
    expect(cursors).toEqual({ results: 20, incoming: "60", outgoing: null });
    expect(mergeHistoryItems([{ id: "same" }], [{ id: "same" }, { id: "older" }])).toEqual([{ id: "same" }, { id: "older" }]);
  });

  it("stops a load-all cursor loop when a server repeats its cursor", () => {
    expect(() => advanceHistoryCursors(
      { results: 20, incoming: null, outgoing: null },
      { results: { nextBefore: 20 }, incoming: {}, outgoing: {} },
    )).toThrow("Kurzor historie se neoposunul.");
  });
});
