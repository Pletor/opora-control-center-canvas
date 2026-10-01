import { describe, expect, it } from "vitest";
import { pickVerdict, badgeView, type SyncCheck, type SyncReport, type SyncVerdict } from "./sync-badge";

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

function report(verdicts: SyncVerdict[]): SyncReport {
  return {
    project: "p",
    workspace: "draft",
    observedAt: "2026-09-17T00:00:00Z",
    gitHead: null,
    signals: [],
    verdicts,
    counts: {},
  };
}

describe("pickVerdict", () => {
  it("vrátí null, když report chybí", () => {
    expect(pickVerdict(null, "n1")).toBeNull();
  });

  it("vrátí null, když uzel chybí", () => {
    expect(pickVerdict(report([verdict()]), null)).toBeNull();
  });

  it("vrátí null, když uzel v reportu není", () => {
    expect(pickVerdict(report([verdict({ scope: { kind: "node", id: "jiny" } })]), "n1")).toBeNull();
  });

  it("nepřebere verdikt sektoru se stejným id", () => {
    expect(pickVerdict(report([verdict({ scope: { kind: "sector", id: "n1" } })]), "n1")).toBeNull();
  });

  it("najde verdikt daného uzlu", () => {
    const v = verdict({ scope: { kind: "node", id: "n1" } });
    expect(pickVerdict(report([verdict({ scope: { kind: "node", id: "jiny" } }), v]), "n1")).toBe(v);
  });
});

describe("badgeView", () => {
  it("vrátí null bez verdiktu", () => {
    expect(badgeView(null)).toBeNull();
  });

  it("zelené: smí se, sedí zadání, kód, testy a důkaz", () => {
    const view = badgeView(verdict({ state: "green", canCommit: true, canMerge: true }));
    expect(view).toEqual({
      tone: "green", label: "Zelené", detail: "Zadání, kód, testy a důkaz sedí.", steps: [], checks: [],
    });
  });

  it("rozpracováno: tichý tón", () => {
    const view = badgeView(verdict({ state: "draft", canCommit: true, canMerge: false }));
    expect(view?.tone).toBe("muted");
    expect(view?.label).toBe("Rozpracováno");
  });

  it("uzavřeno: tichý tón, i když canCommit a canMerge jsou nepravda", () => {
    const view = badgeView(verdict({ state: "closed", canCommit: false, canMerge: false, checks: [], blocking: [] }));
    expect(view?.tone).toBe("muted");
    expect(view?.label).toBe("Uzavřeno");
  });

  it("čeká na 1:1 se správným tvarem pro 1 neprošlou kontrolu", () => {
    const view = badgeView(verdict({
      state: "waiting", canCommit: true, canMerge: false,
      checks: [check("spec", true), check("pair", false, "spec-ahead")],
    }));
    expect(view?.tone).toBe("amber");
    expect(view?.label).toBe("Čeká na 1:1");
    expect(view?.detail).toBe("Neprošla 1 kontrola.");
  });

  it("čeká na 1:1 se správným tvarem pro 2 neprošlé kontroly", () => {
    const view = badgeView(verdict({
      state: "waiting", canCommit: true, canMerge: false,
      checks: [check("a", false), check("b", false), check("c", true)],
    }));
    expect(view?.detail).toBe("Neprošly 2 kontroly.");
  });

  it("čeká na 1:1 se správným tvarem pro 5 neprošlých kontrol", () => {
    const view = badgeView(verdict({
      state: "waiting", canCommit: true, canMerge: false,
      checks: [check("a", false), check("b", false), check("c", false), check("d", false), check("e", false)],
    }));
    expect(view?.detail).toBe("Neprošlo 5 kontrol.");
  });

  it("canCommit false s blokujícím vysokým echem nese červený tón a zákaz commitu", () => {
    const view = badgeView(verdict({
      state: "waiting", canCommit: false, canMerge: false,
      checks: [check("source", false, "source-missing")],
      blocking: ["sha256-abc"],
    }));
    expect(view?.tone).toBe("red");
    expect(view?.label).toBe("Nesmí se commitnout");
  });

  it("steps a checks jdou beze změny z verdiktu", () => {
    const checks = [check("spec", false, "opora-uncommitted")];
    const nextSteps = ["potvrď commit"];
    const view = badgeView(verdict({ state: "waiting", checks, nextSteps }));
    expect(view?.steps).toBe(nextSteps);
    expect(view?.checks).toBe(checks);
  });
});
