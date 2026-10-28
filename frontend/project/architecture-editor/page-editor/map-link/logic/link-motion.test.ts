import { describe, expect, it } from "vitest";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import type { StudioJourney } from "@/project/studio/logic/studio-status";
import type { DerivedJourney } from "../../../domain-map/logic/derived-journeys";
import { hopEdges, mapMotion, pageOfCard, routeEdges, type MapPlace } from "./link-motion";

const card = (id: string, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId: "home", name: id, purpose: "", kind: "node", x: 0, y: 0, ...extra });
const edge = (id: string, source: string, target: string, extra: Partial<GraphEdge> = {}): GraphEdge => ({ id, source, target, ...extra });
const place: MapPlace = {
  pageId: "home",
  cards: [card("button"), card("form"), card("pay", { site: { kind: "page", path: "/pay" } })],
  edges: [edge("e1", "button", "pay", { carries: "navigation" }), edge("e2", "button", "form", { carries: "data" }), edge("rule", "form", "pay", { port: "rule" })],
};
const derived = (extra: Partial<DerivedJourney> = {}): DerivedJourney => ({ applicationId: "web", id: "j", missing: [], segments: [{ from: "s1", to: "s2", line: "", realized: true }], ...extra });
const journey = (run?: DerivedJourney): StudioJourney => ({ id: "j", name: "Nákup", domainId: "web", pages: new Set(["home", "pay"]), stepPages: new Map([["s0", "nav"], ["s1", "home"], ["s2", "pay"]]), derived: run });

describe("map link motion", () => {
  it("places a sub-page on itself and other cards on the open page", () => {
    expect(pageOfCard(place.cards[2], "home")).toBe("pay");
    expect(pageOfCard(place.cards[0], "home")).toBe("home");
  });

  it("finds next edges that realise a hop between step pages", () => {
    expect(hopEdges(place, journey(), { from: "s1", to: "s2" })).toEqual(["e1"]);
    expect(hopEdges(place, journey(), { from: "s0", to: "s1" })).toEqual([]);
    expect(hopEdges(place, journey(), { from: "s1", to: "s1" })).toEqual([]);
    expect(routeEdges(place, journey(derived()))).toEqual(["e1"]);
  });

  it("moves dots only on next edges touching a building card", () => {
    const motion = mapMotion(place, new Map([["form", "building"]]), [], null);
    expect([...motion.links.keys()]).toEqual(["e2"]);
    expect(motion.links.get("e2")).toEqual({ building: 0, pass: null, failure: null });
  });

  it("replays a fresh pass once along the route and pulses its cards", () => {
    const motion = mapMotion(place, new Map(), [{ stamp: "web/j@t", journey: journey(derived()) }], null);
    expect(motion.links.get("e1")?.pass).toEqual({ stamp: "web/j@t", delay: 0 });
    expect([...motion.pulsing].sort()).toEqual(["button", "pay"]);
  });

  it("stops a red dot on the edge of the first failure", () => {
    const failed = journey(derived({ lastRun: { at: "t", passed: false, stale: false, command: "x", failed: 1, firstFailure: { from: "s1", to: "s2", reason: "timeout" } } }));
    const motion = mapMotion(place, new Map(), [], [failed]);
    expect(motion.links.get("e1")?.failure?.title).toBe("Cesta Nákup spadla na přechodu s1 → s2: timeout");
    expect(motion.links.has("e2")).toBe(false);
  });

  it("circles dots on the edges of the hop a running journey is replaying", () => {
    const running = journey(derived({ running: { runId: "r", at: "t", segment: { from: "s1", to: "s2" } } }));
    const motion = mapMotion(place, new Map(), [], [running]);
    expect(motion.links.get("e1")?.running?.title).toBe("Cesta Nákup právě běží: přechod s1 → s2");
    expect(motion.links.has("e2")).toBe(false);
    expect(mapMotion(place, new Map(), [], [journey(derived({ running: { runId: "r", at: "t", segment: null } }))]).links.size).toBe(0);
  });
});
