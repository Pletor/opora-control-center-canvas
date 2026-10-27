import { describe, expect, it } from "vitest";
import type { ApplicationSite, CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DerivedJourney } from "../../../domain-map/logic/derived-journeys";
import { pageSlices, sectionChips } from "./page-slice";

const page = (id: string, parentId: string | null = "app", extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, parentId, kind: "node", name: id[0].toUpperCase() + id.slice(1), purpose: "", x: 0, y: 0, site: { kind: "page", path: "/" + id }, ...extra });

const pages = [
  page("uvod"), page("realizace", "app", { site: { kind: "page", path: "/realizace", sections: [{ id: "cta", role: "cta", name: "Výzva", intent: "" }] } }),
  page("kontakt", "app", { site: { kind: "page", path: "/kontakt", sections: [{ id: "form", role: "form", name: "Formulář", intent: "" }] } }),
  page("dekujeme"), page("cenik"),
];

const site: ApplicationSite = { kind: "application", environments: [], journeys: [
  { id: "poptavka", name: "Poptávka zahrady", actor: "majitel domu", pointA: "neví, kolik to stojí", pointB: "má termín prohlídky", steps: [
    { id: "s1", page: "nav", via: { do: "open" } },
    { id: "s2", page: "realizace", label: "Důkaz", via: { do: "click", text: "Realizace" } },
    { id: "s3", page: "kontakt", label: "Poptávka", shift: "z „asi“ na „chci prohlídku“", objection: "skryté ceny", via: { do: "click", section: "cta", text: "Chci podobnou zahradu" } },
    { id: "s4", page: "dekujeme", label: "Potvrzení", via: { do: "submit", section: "form", text: "Odeslat" } },
    { id: "s5", page: "cenik", label: "Ceník", after: "s3", via: { do: "click", section: "chybi" } },
  ] },
  { id: "navrat", name: "Návrat", steps: [{ id: "a", page: "kontakt", via: { do: "open" } }, { id: "b", page: "zmizela" }] },
] };

describe("úsek cesty aktivní stránky", () => {
  it("najde krok stránky s rolí, posunem, námitkou, proměnou cesty a sousedy", () => {
    const [slice, second] = pageSlices(site, "kontakt", pages);
    expect(slice).toMatchObject({ journeyId: "poptavka", step: 3, stepCount: 5, role: "Poptávka", shift: "z „asi“ na „chci prohlídku“",
      objection: "skryté ceny", actor: "majitel domu", pointA: "neví, kolik to stojí", pointB: "má termín prohlídky", entry: null });
    expect(slice.from).toEqual({ stepId: "s2", role: "Důkaz", pageId: "realizace", pageLabel: "Realizace", missing: false,
      signal: { text: "klikne na „Chci podobnou zahradu“ v sekci Výzva", missingSection: null }, branch: false, unrealized: null });
    expect(slice.next.map((item) => [item.stepId, item.pageId, item.branch, item.signal?.text])).toEqual([
      ["s4", "dekujeme", false, "odešle formulář „Odeslat“ v sekci Formulář"], ["s5", "cenik", true, "klikne v sekci chybi"]]);
    expect(slice.next[1].signal?.missingSection).toBe("chybi");
    expect(second).toMatchObject({ journeyId: "navrat", step: 1, from: null, entry: "otevře stránku přímo" });
    expect(second.next[0]).toMatchObject({ pageId: null, pageLabel: "chybí stránka zmizela", missing: true, signal: null });
  });

  it("předchozí krok z menu není odkaz na stránku", () => {
    const [slice] = pageSlices(site, "realizace", pages);
    expect(slice.from).toMatchObject({ stepId: "s1", pageId: null, pageLabel: "Menu", missing: false, signal: { text: "klikne na „Realizace“" } });
  });

  it("odbočka zpět ukáže sousedy kroku, ze kterého odbočuje", () => {
    const [slice] = pageSlices(site, "cenik", pages);
    expect(slice.from).toMatchObject({ stepId: "s3", pageId: "kontakt", branch: true });
    expect(slice.next).toEqual([]);
  });

  it("nese nerealizovaný přechod a přerušení cesty z odvození", () => {
    const derived: DerivedJourney = { applicationId: "app", id: "poptavka", missing: [], broken: "chybí krok",
      segments: [{ from: "s2", to: "s3", line: "realizace → kontakt", realized: false }, { from: "s3", to: "s4", line: "kontakt → dekujeme", realized: true }] };
    const [slice] = pageSlices(site, "kontakt", pages, new Map([["poptavka", derived]]));
    expect(slice.broken).toBe("chybí krok");
    expect(slice.from?.unrealized).toBe("realizace → kontakt");
    expect(slice.next[0].unrealized).toBeNull();
  });

  it("stránka mimo cesty a doména bez cest nedají nic", () => {
    expect(pageSlices(site, "uvod", pages)).toEqual([]);
    expect(pageSlices(undefined, "kontakt", pages)).toEqual([]);
  });
});

describe("pruh sekcí", () => {
  const node = (id: string, parentId: string, section?: string): CanvasNode =>
    ({ id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, ...(section ? { card: { section } } : {}) });
  const kontakt = page("kontakt", "app", { site: { kind: "page", path: "/kontakt", sections: [
    { id: "hero", role: "hero", name: "Úvod", intent: "", moves: "uklidní" }, { id: "form", role: "form", name: "Formulář", intent: "" }] } });
  const graph: Graph = { edges: [], nodes: [
    kontakt, { id: "sek", parentId: "kontakt", kind: "sector", name: "sek", purpose: "", x: 0, y: 0 },
    node("banner", "sek", "hero"), node("foto", "kontakt", "hero"), node("pole", "kontakt", "form"),
    page("dekujeme", "kontakt"), node("cizi", "dekujeme", "hero"), node("ztracena", "kontakt", "faq"),
  ] };

  it("počítá komponenty stránky na sekci, podstránku a neznámou sekci nezapočte", () => {
    expect(sectionChips(graph, "kontakt")).toEqual([
      { id: "hero", role: "Úvod", name: "Úvod", moves: "uklidní", components: 2 },
      { id: "form", role: "Formulář", name: "Formulář", components: 1 }]);
  });

  it("stránka bez sekcí nemá pruh", () => {
    expect(sectionChips(graph, "dekujeme")).toEqual([]);
  });

  it("nese odznak ověření cesty z posledního dokladu, bez odvození ne", () => {
    const derived = new Map<string, DerivedJourney>([["poptavka", { applicationId: "app", id: "poptavka", missing: [], segments: [],
      lastRun: { at: "2026-10-27T21:40:00Z", passed: false, stale: false, command: "run", failed: 1, firstFailure: { from: "s2", to: "s3" } } }]]);
    const [slice] = pageSlices(site, "kontakt", pages, derived);
    expect(slice.verification).toMatchObject({ tone: "failed", text: "Neprošlo: s2 → s3" });
    expect(pageSlices(site, "kontakt", pages)[0].verification).toBeUndefined();
  });
});
