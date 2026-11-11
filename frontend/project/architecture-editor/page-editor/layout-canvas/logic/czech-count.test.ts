import { describe, expect, it } from "vitest";
import { czechCount } from "./czech-count";

describe("české skloňování počtu", () => {
  it("jeden, dva až čtyři a ostatní", () => {
    const forms: [string, string, string] = ["prvek", "prvky", "prvků"];
    expect([0, 1, 2, 4, 5].map((count) => czechCount(count, forms))).toEqual(["0 prvků", "1 prvek", "2 prvky", "4 prvky", "5 prvků"]);
  });
});
