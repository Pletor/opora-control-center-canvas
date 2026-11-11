import { describe, expect, it } from "vitest";
import { sketchedBoxes } from "./page-plan";

describe("boxy se skicou z plánu stránky", () => {
  it("jen sekce s kladnou revizí skici; cizí tvar nevadí", () => {
    expect([...sketchedBoxes({ sections: [{ id: "a", sketch: { revision: 2 } }, { id: "b", sketch: null }, { id: "c" }, { id: "d", sketch: { revision: 0 } }, null, "x"] })]).toEqual(["a"]);
    expect(sketchedBoxes(null).size).toBe(0);
    expect(sketchedBoxes({ sections: "nic" }).size).toBe(0);
  });
});
