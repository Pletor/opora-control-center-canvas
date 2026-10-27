import { describe, expect, it } from "vitest";
import { derivedForDomain, derivedJourneysUrl, derivedStepState, normalizeDerivedJourneys } from "./derived-journeys";

describe("odvozené cesty zákazníka", () => {
  it("adresa dotazu nese projekt", () => {
    expect(derivedJourneysUrl("p 1")).toBe("/api/project-architecture/journeys?project=p+1");
  });
  it("čte chybějící stránky, přechody i důvod rozbití a vadné položky zahodí", () => {
    const raw = { journeys: [
      { applicationId: "app", id: "kurz", name: "Kurz", line: "/ → /obsah → /nabidka",
        steps: [{ id: "a", page: "p", path: "/" }, { id: "b", page: "obsah", path: "/obsah" }, { id: "c", page: "nabidka", path: "/nabidka" }],
        segments: [{ from: "a", to: "b", line: "/ → /obsah", realized: true }, { from: "b", to: "c", line: "/obsah → /nabidka", realized: false },
          { from: "x", realized: true }] },
      { applicationId: "app", id: "pryc", name: "Pryč", broken: "chybí stránka x v kroku Upsell.",
        steps: [{ id: "a", page: "nav", path: "nav" }, { id: "b", page: "x", missing: true }] },
      { id: "sirotek" }, null, "x",
    ] };
    expect(normalizeDerivedJourneys(raw)).toEqual([
      { applicationId: "app", id: "kurz", missing: [], segments: [{ from: "a", to: "b", line: "/ → /obsah", realized: true },
        { from: "b", to: "c", line: "/obsah → /nabidka", realized: false }] },
      { applicationId: "app", id: "pryc", missing: ["b"], segments: [], broken: "chybí stránka x v kroku Upsell." },
    ]);
    expect(normalizeDerivedJourneys(null)).toEqual([]);
    expect(normalizeDerivedJourneys({ journeys: "x" })).toEqual([]);
  });
  it("čte poslední doklad přehrání tolerantně a neúplný zahodí", () => {
    const raw = { journeys: [
      { applicationId: "web", id: "a", lastRun: { at: "2026-10-27T21:40:00Z", passed: false, stale: false, command: "run", failed: 1,
        firstFailure: { from: "s2", to: "s3", reason: "URL /novinky" } } },
      { applicationId: "web", id: "b", lastRun: { at: "2026-10-27T21:40:00Z", passed: true, stale: true, firstFailure: { from: "s1" } } },
      { applicationId: "web", id: "c", lastRun: { passed: true } },
    ] };
    const [a, b, c] = normalizeDerivedJourneys(raw);
    expect(a.lastRun).toEqual({ at: "2026-10-27T21:40:00Z", passed: false, stale: false, command: "run", failed: 1,
      firstFailure: { from: "s2", to: "s3", reason: "URL /novinky" } });
    expect(b.lastRun).toEqual({ at: "2026-10-27T21:40:00Z", passed: true, stale: true, command: "", failed: 0 });
    expect(c.lastRun).toBeUndefined();
  });
  it("vybere cesty jedné domény podle id", () => {
    const items = [{ applicationId: "a", id: "j", missing: [], segments: [] }, { applicationId: "b", id: "j", missing: ["s"], segments: [] }];
    expect(derivedForDomain(items, "b").get("j")?.missing).toEqual(["s"]);
    expect(derivedForDomain(items, "c").size).toBe(0);
  });
  it("u kroku řekne, že chybí stránka nebo vazba z předchozího kroku", () => {
    const derived = { applicationId: "a", id: "j", missing: ["d"], segments: [{ from: "a", to: "b", line: "/a → /b", realized: false },
      { from: "b", to: "c", line: "/b → X → /c", realized: true }] };
    expect(derivedStepState(derived, "b")).toEqual({ missing: false, unrealized: "/a → /b" });
    expect(derivedStepState(derived, "c")).toEqual({ missing: false, unrealized: null });
    expect(derivedStepState(derived, "d")).toEqual({ missing: true, unrealized: null });
    expect(derivedStepState(undefined, "b")).toEqual({ missing: false, unrealized: null });
  });
});
