import { describe, expect, it } from "vitest";
import type { StudioLink } from "../../logic/studio-level";
import type { StudioState } from "../../logic/studio-status";
import { buildingLinks, cycleMs, levelMotion, loopProgress, MAX_ANIMATED_LINKS, onceProgress, passDurationMs } from "./motion-plan";

const link = (source: string, target: string): StudioLink => ({ id: `${source}->${target}`, source, target, count: 1, carries: "navigation", kinds: { navigation: 1 }, edgeIds: [] });

describe("motion plan", () => {
  it("staggers the cycle by 70 ms per link, repeating every four links", () => {
    expect([0, 1, 2, 3, 4, 5].map(cycleMs)).toEqual([1050, 1120, 1190, 1260, 1050, 1120]);
  });

  it("spreads two dots evenly along the route and moves them linearly", () => {
    expect(loopProgress(0, 1000, 0, 2)).toBe(0);
    expect(loopProgress(0, 1000, 1, 2)).toBe(0.5);
    expect(loopProgress(250, 1000, 0, 2)).toBe(0.25);
    expect(loopProgress(750, 1000, 1, 2)).toBe(0.25);
    expect(loopProgress(2250, 1000, 0, 2)).toBe(0.25);
  });

  it("shows a one-shot dot only between its start and end", () => {
    expect(onceProgress(100, 100, 500, 1000)).toBeNull();
    expect(onceProgress(1100, 100, 500, 1000)).toBe(0.5);
    expect(onceProgress(1700, 100, 500, 1000)).toBeNull();
  });

  it("animates only links touching a card that is being built, at most 40", () => {
    const states = new Map<string, StudioState>([["a", "building"], ["b", "done"], ["c", "plan"], ["d", "building"]]);
    expect([...buildingLinks([link("a", "b"), link("b", "c"), link("c", "d")], states)]).toEqual([["a->b", 0], ["c->d", 1]]);
    const many = Array.from({ length: 50 }, (_, index) => link("a", "x" + index));
    expect(buildingLinks(many, states).size).toBe(MAX_ANIMATED_LINKS);
  });

  it("combines building dots, a one-shot pass in route order and a failure per link", () => {
    const states = new Map<string, StudioState>([["a", "building"]]);
    const motion = levelMotion({
      links: [link("a", "b"), link("b", "c")], states,
      passes: [{ stamp: "web/j@1", links: ["a->b", "b->c"] }],
      failures: [{ linkId: "b->c", title: "spadlo" }],
    });
    expect(motion.get("a->b")).toEqual({ building: 0, pass: { stamp: "web/j@1", delay: 0 }, failure: null });
    expect(motion.get("b->c")).toEqual({ building: null, pass: { stamp: "web/j@1", delay: 1050 }, failure: { title: "spadlo" } });
    expect(levelMotion({ links: [link("b", "c")], states, passes: [], failures: [] }).size).toBe(0);
  });

  it("lasts as long as the route, but at least one card pulse", () => {
    expect(passDurationMs(0)).toBe(900);
    expect(passDurationMs(3)).toBe(3150);
  });
});
