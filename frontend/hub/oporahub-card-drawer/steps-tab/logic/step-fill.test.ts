import { describe, expect, it } from "vitest";
import { stepFill } from "./step-fill";

const rows = (...status: ("done" | "failed" | "skipped" | "after_merge" | "current" | "waiting")[]) => status.map((s) => ({ status: s }));

describe("stepFill", () => {
  it("bez kroků je výplň prázdná a klidná", () => expect(stepFill([])).toEqual({ ratio: 0, percent: 0, severity: "normal" }));
  it("podíl počítá hotové a přeskočené kroky", () => expect(stepFill(rows("done", "waiting", "current", "waiting")).percent).toBe(25));
  it("všechny hotové jsou 100 %", () => expect(stepFill(rows("done", "done"))).toEqual({ ratio: 1, percent: 100, severity: "normal" }));
  it("přeskočený krok je varování", () => expect(stepFill(rows("done", "skipped", "waiting")).severity).toBe("warn"));
  it("selhaný krok je chyba a přebije varování", () => expect(stepFill(rows("skipped", "failed")).severity).toBe("error"));
  it("krok uznaný sloučením plní lištu, ale jantarově", () =>
    expect(stepFill(rows("done", "after_merge"))).toEqual({ ratio: 1, percent: 100, severity: "warn" }));
});
