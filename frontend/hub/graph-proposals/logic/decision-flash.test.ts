import { describe, expect, it } from "vitest";
import { flashEnded, flashFor, flashModifier } from "./decision-flash";

describe("decision flash on proposal history rows", () => {
  it("pulses the accepted row and shakes the refused one", () => {
    expect(flashModifier(flashFor("p1", "accepted"), "p1")).toBe("graph-proposals__entry--accepted");
    expect(flashModifier(flashFor("p1", "refused"), "p1")).toBe("graph-proposals__entry--refused");
  });
  it("leaves other rows and an empty id untouched", () => {
    expect(flashModifier(flashFor("p1", "accepted"), "p2")).toBe("");
    expect(flashFor("", "accepted")).toBeNull();
    expect(flashModifier(null, "p1")).toBe("");
  });
  it("clears only when the flashing row finishes its animation", () => {
    const flash = flashFor("p1", "refused");
    expect(flashEnded(flash, "p2")).toBe(flash);
    expect(flashEnded(flash, "p1")).toBeNull();
    expect(flashEnded(null, "p1")).toBeNull();
  });
});
