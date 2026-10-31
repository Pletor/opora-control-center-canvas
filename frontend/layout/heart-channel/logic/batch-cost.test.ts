import { describe, expect, it } from "vitest";
import { batchRows, formatCost } from "./batch-cost";

describe("cena dávky", () => {
  it("formátuje USD česky", () => {
    expect(formatCost(0.1234)).toBe("0,12 USD");
    expect(formatCost(1.5)).toBe("1,50 USD");
    expect(formatCost(0)).toBe("0,00 USD");
    expect(formatCost(0.001)).toBe("< 0,01 USD");
    expect(formatCost(null)).toBe("—");
    expect(formatCost(undefined)).toBe("—");
  });

  it("dávky jdou od nejnovější a bez shrnutí řeknou stav", () => {
    const rows = batchRows([
      { at: "a", status: "ok", costUsd: 0.05, summary: "Naplánoval 3 úkoly." },
      { at: "b", status: "rate_limited", costUsd: null, summary: null },
      { at: "c", status: "ok", costUsd: 0.01, summary: "  " },
    ]);
    expect(rows.map((r) => r.summary)).toEqual(["Bez shrnutí", "Limit předplatného", "Naplánoval 3 úkoly."]);
    expect(rows.map((r) => r.cost)).toEqual(["0,01 USD", "—", "0,05 USD"]);
    expect(rows.map((r) => r.range)).toEqual([null, null, null]);  // bez trvání se kroky nerozbalí
  });

  it("dávka s trváním nese rozsah kroků", () => {
    const [row] = batchRows([{ at: "2026-10-31T10:00:00Z", status: "ok", costUsd: 0.02, summary: "Hotovo.", durationMs: 4000 }]);
    expect(row.range).toEqual({ since: "2026-10-31T10:00:00Z", until: "2026-10-31T10:00:05.000Z" });
  });
});
