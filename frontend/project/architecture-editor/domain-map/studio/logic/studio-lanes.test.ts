import { describe, expect, it } from "vitest";
import type { ApplicationSite, CanvasNode } from "@/shared/types/logic/types";
import type { DerivedJourney } from "../../logic/derived-journeys";
import { studioLanes, transitionState } from "./studio-lanes";

const page = (id: string, name: string, path: string): CanvasNode =>
  ({ id, parentId: "web", name, purpose: "", kind: "node", x: 0, y: 0, site: { kind: "page", path, sections: [{ id: "cta", role: "cta", name: "Výzva", intent: "" }] } });
const pages = [page("p1", "Pěstování", "/pestovani"), page("p2", "Kontakt", "/kontakt")];
const site: ApplicationSite = { kind: "application", environments: [], journeys: [{
  id: "j1", name: "Kampaň", pointA: "Neví", pointB: "Ví",
  steps: [
    { id: "s1", page: "nav" },
    { id: "s2", page: "p1", label: "Zájem" },
    { id: "s3", page: "p2", via: { do: "submit", section: "cta", text: "Odeslat" } },
    { id: "s4", page: "gone", after: "s2", via: { do: "click", section: "nic" } },
  ],
}] };
const derived = (lastRun?: DerivedJourney["lastRun"], broken?: string): DerivedJourney => ({
  applicationId: "web", id: "j1", missing: ["s4"], ...(broken ? { broken } : {}), ...(lastRun ? { lastRun } : {}),
  segments: [
    { from: "s1", to: "s2", line: "nav → /pestovani", realized: true },
    { from: "s2", to: "s3", line: "/pestovani → /kontakt", realized: false },
  ],
});
const run = (extra: Partial<NonNullable<DerivedJourney["lastRun"]>>) => ({ at: "2026-10-27T10:00:00Z", passed: false, stale: false, command: "npx playwright", failed: 1, ...extra });

describe("transitionState", () => {
  it("reads the last run: none, stale, passed, the first failure and the rest unproven", () => {
    expect(transitionState(undefined, "s1", "s2")).toBe("unverified");
    expect(transitionState(derived(), "s1", "s2")).toBe("unverified");
    expect(transitionState(derived(run({ stale: true, passed: true })), "s1", "s2")).toBe("stale");
    expect(transitionState(derived(run({ passed: true, failed: 0 })), "s1", "s2")).toBe("passed");
    const failed = derived(run({ firstFailure: { from: "s2", to: "s3", reason: "timeout" } }));
    expect(transitionState(failed, "s2", "s3")).toBe("failed");
    expect(transitionState(failed, "s1", "s2")).toBe("unverified");
    expect(transitionState(derived(run({ passed: true }), "chybí stránka"), "s1", "s2")).toBe("unverified");
  });
});

describe("studioLanes", () => {
  const [lane] = studioLanes(site, pages, new Map([["j1", derived(run({ firstFailure: { from: "s2", to: "s3", reason: "timeout" } }))]]));

  it("turns steps into stops: menu, page with name and path, missing page", () => {
    expect(lane.stops).toEqual([
      { stepId: "s1", role: "1. krok", title: "Menu", path: "nav", pageId: null, missing: false },
      { stepId: "s2", role: "Zájem", title: "Pěstování", path: "/pestovani", pageId: "p1", missing: false },
      { stepId: "s3", role: "3. krok", title: "Kontakt", path: "/kontakt", pageId: "p2", missing: false },
      { stepId: "s4", role: "4. krok", title: "chybí stránka gone", path: "", pageId: null, missing: true },
    ]);
  });

  it("gives each transition its signal, branch, realization and verification state", () => {
    expect(lane.transitions.map((item) => [item.from, item.to, item.realized, item.state])).toEqual([
      ["s1", "s2", true, "unverified"], ["s2", "s3", false, "failed"], ["s2", "s4", null, "unverified"]]);
    expect(lane.transitions[1]).toMatchObject({ signal: "odešle formulář „Odeslat“ v sekci Výzva", missingSection: null, branchFrom: null, line: "/pestovani → /kontakt", reason: "timeout" });
    expect(lane.transitions[2]).toMatchObject({ branchFrom: "Zájem", missingSection: "nic", reason: null });
  });

  it("works without derived data and without journeys", () => {
    const [bare] = studioLanes(site, pages, new Map());
    expect(bare.derived).toBeUndefined();
    expect(bare.transitions.every((item) => item.realized === null && item.state === "unverified")).toBe(true);
    expect(studioLanes(undefined, pages, new Map())).toEqual([]);
  });
});
