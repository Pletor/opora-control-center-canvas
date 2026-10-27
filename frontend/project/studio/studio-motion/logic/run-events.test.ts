import { describe, expect, it } from "vitest";
import type { JourneyLastRun } from "@/project/architecture-editor/domain-map/logic/derived-journeys";
import type { StudioJourney } from "../../logic/studio-status";
import { freshPasses, journeyKey, runFailures, runStamps } from "./run-events";

const journey = (id: string, lastRun?: Partial<JourneyLastRun>): StudioJourney => ({
  id, name: "Kampaň " + id, domainId: "web", pages: new Set(), stepPages: new Map(),
  derived: { applicationId: "web", id, missing: [], segments: [], ...(lastRun ? { lastRun: { at: "t1", passed: true, stale: false, command: "x", failed: 0, ...lastRun } } : {}) },
});

describe("run events", () => {
  it("never replays anything on the first load", () => {
    expect(freshPasses(null, [journey("a", {})])).toEqual([]);
  });

  it("reports a journey whose new proof passed and is not stale", () => {
    const before = runStamps([journey("a", { at: "t1" }), journey("b"), journey("c", { at: "t1" }), journey("d", { at: "t1" })]);
    const now = [journey("a", { at: "t1" }), journey("b", { at: "t2" }), journey("c", { at: "t2", passed: false }), journey("d", { at: "t2", stale: true })];
    expect(freshPasses(before, now).map(journeyKey)).toEqual(["web/b"]);
    expect(freshPasses(runStamps(now), now)).toEqual([]);
  });

  it("explains the first failure of a journey that did not pass", () => {
    const failed = journey("a", { passed: false, failed: 1, firstFailure: { from: "vstup", to: "prodej", reason: "chybí tlačítko" } });
    const stale = journey("b", { passed: false, stale: true, firstFailure: { from: "x", to: "y" } });
    expect(runFailures([failed, stale, journey("c", {}), journey("d", { passed: false })]).map(({ from, to, title }) => ({ from, to, title }))).toEqual([
      { from: "vstup", to: "prodej", title: "Cesta Kampaň a spadla na přechodu vstup → prodej: chybí tlačítko" },
      { from: "x", to: "y", title: "Cesta Kampaň b spadla na přechodu x → y (doklad je starší než mapa)" },
    ]);
  });
});
