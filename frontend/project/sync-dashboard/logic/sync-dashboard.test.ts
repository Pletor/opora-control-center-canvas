import { describe, expect, it } from "vitest";
import { dashboardView } from "./sync-dashboard";
import type { SyncCheck, SyncReport, SyncSignal, SyncVerdict } from "@/shared/desktop-state/logic/types";

function check(id: string, passed: boolean, signal: string | null = null): SyncCheck {
  return { id, name: id, passed, signal };
}

function verdict(overrides: Partial<SyncVerdict> = {}): SyncVerdict {
  return {
    scope: { kind: "node", id: "n1" },
    state: "draft",
    canCommit: true,
    canMerge: false,
    checks: [],
    blocking: [],
    nextSteps: [],
    ...overrides,
  };
}

function signal(overrides: Partial<SyncSignal> = {}): SyncSignal {
  return {
    id: "sig",
    type: "spec-ahead",
    severity: "low",
    subject: { scope: null, id: null, path: null, specRevision: null },
    evidence: { expected: "", actual: "", source: "" },
    action: "",
    ...overrides,
  };
}

function report(overrides: Partial<SyncReport> = {}): SyncReport {
  return {
    project: "p",
    workspace: "draft",
    observedAt: "2026-09-17T00:00:00Z",
    gitHead: "abc123",
    signals: [],
    verdicts: [],
    counts: {},
    ...overrides,
  };
}

describe("dashboardView", () => {
  it("vrátí null, když report chybí", () => {
    expect(dashboardView(null, {})).toBeNull();
  });

  it("seřadí řádky: nejdřív čeká, potom rozpracováno, zelené, uzavřeno; uvnitř skupiny podle jména", () => {
    const verdicts = [
      verdict({ scope: { kind: "node", id: "g1" }, state: "green" }),
      verdict({ scope: { kind: "node", id: "d1" }, state: "closed" }),
      verdict({ scope: { kind: "node", id: "w-zeta" }, state: "waiting" }),
      verdict({ scope: { kind: "node", id: "w-alfa" }, state: "waiting" }),
      verdict({ scope: { kind: "node", id: "r1" }, state: "draft" }),
    ];
    const names = { "w-zeta": "Zeta", "w-alfa": "Alfa" };
    const view = dashboardView(report({ verdicts }), names);
    expect(view?.rows.map((row) => row.id)).toEqual(["w-alfa", "w-zeta", "r1", "g1", "d1"]);
  });

  it("spočítá řádky podle stavu", () => {
    const verdicts = [
      verdict({ scope: { kind: "node", id: "a" }, state: "green" }),
      verdict({ scope: { kind: "node", id: "b" }, state: "green" }),
      verdict({ scope: { kind: "node", id: "c" }, state: "waiting" }),
      verdict({ scope: { kind: "node", id: "d" }, state: "draft" }),
      verdict({ scope: { kind: "node", id: "e" }, state: "draft" }),
      verdict({ scope: { kind: "node", id: "f" }, state: "draft" }),
      verdict({ scope: { kind: "node", id: "g" }, state: "closed" }),
    ];
    const view = dashboardView(report({ verdicts }), {});
    expect(view?.totals).toEqual({ green: 2, waiting: 1, draft: 3, closed: 1 });
  });

  it("spočítá echo podle závažnosti", () => {
    const signals = [
      signal({ severity: "high" }),
      signal({ severity: "high" }),
      signal({ severity: "medium" }),
      signal({ severity: "low" }),
      signal({ severity: "low" }),
      signal({ severity: "low" }),
    ];
    const view = dashboardView(report({ signals }), {});
    expect(view?.bySeverity).toEqual({ high: 2, medium: 1, low: 3 });
  });

  it("vybere pět nejčastějších typů echa, sestupně, s abecedním rozhodčím při shodě", () => {
    const types = [
      ...Array(5).fill("spec-ahead"),
      ...Array(4).fill("source-missing"),
      ...Array(2).fill("duplicate-path"),
      ...Array(2).fill("checks-unknown"),
      "doc-path-missing",
      "base-stale",
    ];
    const signals = types.map((type) => signal({ type }));
    const view = dashboardView(report({ signals }), {});
    expect(view?.topSignals).toEqual([
      { type: "spec-ahead", count: 5 },
      { type: "source-missing", count: 4 },
      { type: "checks-unknown", count: 2 },
      { type: "duplicate-path", count: 2 },
      { type: "base-stale", count: 1 },
    ]);
  });

  it("použije id rozsahu, když jméno v mapě chybí", () => {
    const verdicts = [verdict({ scope: { kind: "sector", id: "bez-jmena" } })];
    const view = dashboardView(report({ verdicts }), { jiny: "Jiný" });
    expect(view?.rows[0]?.name).toBe("bez-jmena");
  });

  it("vezme neprošlé kontroly jako failed a první další krok jako nextStep", () => {
    const verdicts = [
      verdict({
        checks: [check("spec", true), check("pair", false, "spec-ahead"), check("checks", false, "checks-unknown")],
        nextSteps: ["spusť testy a zapiš výsledek", "doplň důkaz"],
      }),
    ];
    const view = dashboardView(report({ verdicts }), {});
    expect(view?.rows[0]?.failed).toEqual(["pair", "checks"]);
    expect(view?.rows[0]?.nextStep).toBe("spusť testy a zapiš výsledek");
  });

  it("nextStep je null, když žádný další krok není", () => {
    const view = dashboardView(report({ verdicts: [verdict({ nextSteps: [] })] }), {});
    expect(view?.rows[0]?.nextStep).toBeNull();
  });

  it("předá observedAt a gitHead z reportu", () => {
    const view = dashboardView(report({ observedAt: "2026-09-17T08:00:00Z", gitHead: "deadbee" }), {});
    expect(view?.observedAt).toBe("2026-09-17T08:00:00Z");
    expect(view?.gitHead).toBe("deadbee");
  });
});
