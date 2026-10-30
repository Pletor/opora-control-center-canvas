import { describe, expect, it } from "vitest";
import { gaugeBadge } from "./card-gauge-badge";

const gauge = (extra: Record<string, unknown> = {}) => ({
  steps: { total: 3, done: 2, percent: 67 }, dod: { met: 4, total: 7, percent: 57 }, risk: { level: "standard", reasons: [] },
  evidence: "ok", run: { label: "S", model: "sonnet", advisor: "opus" }, ...extra,
});

describe("odznak měřáku karty", () => {
  it("štítek, % kroků a % DoD; riziko standard se nekreslí", () => {
    const badge = gaugeBadge(gauge())!;
    expect(badge).toMatchObject({ label: "S", thin: false, steps: 67, dod: 57, risk: null });
    expect(badge.title).toBe("Složitost S · kroky 2/3 (67 %) · DoD 57 % · model sonnet + poradce opus");
  });

  it("zvýšené a kritické riziko nese i důvody v titulku", () => {
    const badge = gaugeBadge(gauge({ risk: { level: "critical", reasons: ["sensitive_path:migrations/**"] } }))!;
    expect(badge.risk).toBe("critical");
    expect(badge.title).toContain("kritické riziko (sensitive_path:migrations/**)");
  });

  it("chudé podklady = „?“ s výzvou doplnit kroky a soubory", () => {
    const badge = gaugeBadge(gauge({ evidence: "thin", run: { label: "?", model: "sonnet", advisor: "opus" } }))!;
    expect(badge.thin).toBe(true);
    expect(badge.title.startsWith("Složitost ? – málo podkladů")).toBe(true);
  });

  it("bez gauge nebo s neznámým štítkem odznak není", () => {
    expect(gaugeBadge(undefined)).toBeNull();
    expect(gaugeBadge({ run: { label: "XXL" } })).toBeNull();
    expect(gaugeBadge({ steps: {} })).toBeNull();
  });

  it("chybějící kroky nebo DoD jsou null, ne odhad", () => {
    expect(gaugeBadge({ run: { label: "M" } })).toMatchObject({ label: "M", steps: null, dod: null, risk: null, title: "Složitost M" });
  });
});
