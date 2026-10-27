import { describe, expect, it } from "vitest";
import type { DerivedJourney, JourneyLastRun } from "./derived-journeys";
import { verificationBadge, verificationTime, verificationTitle } from "./journey-verification";

const base: DerivedJourney = { applicationId: "web", id: "kampan", missing: [], segments: [] };
const run = (extra: Partial<JourneyLastRun> = {}): DerivedJourney =>
  ({ ...base, lastRun: { at: "2026-10-27T21:40:00Z", passed: true, stale: false, command: "journey_run", failed: 0, ...extra } });

describe("odznak ověření cesty", () => {
  it("bez odvození nebo u rozbité cesty nic neukáže", () => {
    expect(verificationBadge(undefined)).toBeNull();
    expect(verificationBadge({ ...base, broken: "chybí stránka x" })).toBeNull();
  });
  it("cesta bez dokladu je neověřená", () => {
    expect(verificationBadge(base)).toEqual({ tone: "none", text: "Neověřeno", at: null, command: null });
  });
  it("prošlý čerstvý doklad je ověření", () => {
    expect(verificationBadge(run())).toEqual({ tone: "ok", text: "Ověřeno", at: "2026-10-27T21:40:00Z", command: "journey_run" });
  });
  it("zastaralý doklad má přednost před výsledkem", () => {
    expect(verificationBadge(run({ stale: true }))?.text).toBe("Ověření zastaralé");
    expect(verificationBadge(run({ stale: true, passed: false, failed: 1 }))?.tone).toBe("stale");
  });
  it("neprošlý doklad jmenuje první přechod a důvod", () => {
    expect(verificationBadge(run({ passed: false, failed: 1, firstFailure: { from: "s2", to: "s3", reason: "URL /novinky" } }))?.text)
      .toBe("Neprošlo: s2 → s3 (URL /novinky)");
    expect(verificationBadge(run({ passed: false, failed: 1, firstFailure: { from: "s2", to: "s3" } }))?.text).toBe("Neprošlo: s2 → s3");
    expect(verificationBadge(run({ passed: false }))?.text).toBe("Neprošlo: doklad nepokrývá všechny přechody");
  });
  it("čas a popisek běhu", () => {
    expect(verificationTime(null)).toBe("");
    expect(verificationTime("x")).toBe("");
    expect(verificationTime("2026-10-27T21:40:00Z", "cs-CZ", "UTC")).toContain("21:40");
    const badge = verificationBadge(run())!;
    expect(verificationTitle(badge, "UTC")).toMatch(/^Ověřeno · běh .*21:40 · příkaz: journey_run$/);
    expect(verificationTitle(verificationBadge(base)!)).toBe("Neověřeno");
  });
});
