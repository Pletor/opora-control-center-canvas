import { describe, expect, it } from "vitest";
import { blockerOf, buildLanes, phaseTrail, stableOrder, type CardSnapshot } from "./lanes";
import { flow } from "./fixtures";

const card = (nodeId: string, extra: Partial<CardSnapshot> = {}): CardSnapshot =>
  ({ nodeId, stage: "work", health: "ok", reason: "", executionId: null, ...extra });
const options = { names: { a: "Karta A", b: "Karta B" }, officeConnected: true };

describe("lanes: card snapshot + events → rows of the flow map", () => {
  it("puts each card in the phase of its newest event and keeps the trail of earlier phases", () => {
    const events = [flow(1, "a", "card.status", "intake", "ok"), flow(2, "a", "plan.commit", "plan", "ok"),
      flow(3, "a", "run.claim", "work", "start", { source: "office", worker: "Vývojář 1" })];
    const [lane] = buildLanes([], events, options);
    expect(lane).toMatchObject({ nodeId: "a", title: "Karta A", phase: 2, marker: "run", workerName: "Vývojář 1", source: "office" });
    expect(lane.trail.slice(0, 3)).toEqual(["ok", "ok", "seen"]);
    expect(lane.events.map((event) => event.id)).toEqual([3, 2, 1]);
  });
  it("memory.recall is a read and never moves the marker", () => {
    const [lane] = buildLanes([], [flow(1, "a", "tool.use", "work", "progress"), flow(2, "a", "memory.recall", "memory", "ok")], options);
    expect(lane.phase).toBe(2);
    expect(lane.trail[6]).toBe("ok");
  });
  it("orders blockers first, then by the newest event", () => {
    const events = [flow(1, "a", "needs.input", "plan", "blocked"), flow(2, "b", "tool.use", "work", "progress"), flow(3, "c", "tool.use", "work", "progress")];
    expect(buildLanes([], events, options).map((lane) => lane.nodeId)).toEqual(["a", "c", "b"]);
  });
  it("falls back to the snapshot (stage → phase, lastEventAt) for a card without events in the window", () => {
    const cards = [card("q", { stage: "review", executionId: "ex-1", lastEventAt: "2026-10-22T09:00:00Z" }), card("idle")];
    const lanes = buildLanes(cards, [], options);
    expect(lanes.map((lane) => lane.nodeId)).toEqual(["q"]);
    expect(lanes[0]).toMatchObject({ phase: 4, marker: "none", last: null, lastMs: Date.parse("2026-10-22T09:00:00Z") });
  });
  it("greys out office rows when the office is silent", () => {
    const [lane] = buildLanes([], [flow(1, "a", "tool.use", "work", "progress", { source: "office" })], { ...options, officeConnected: false });
    expect(lane).toMatchObject({ stale: true, marker: "stale" });
  });
  it("names the blocker from the newest event, or from a blocking snapshot", () => {
    expect(blockerOf(flow(1, "a", "pr.checks", "checks", "fail"), null)).toMatchObject({ label: "CI selhalo", tone: "bad" });
    expect(blockerOf(flow(1, "a", "pr.review", "review", "wait"), null)).toMatchObject({ label: "změny požadovány", human: true });
    expect(blockerOf(flow(1, "a", "tool.use", "work", "progress"), null)).toBeNull();
    expect(blockerOf(null, card("a", { health: "blocking" }))).toMatchObject({ label: "blokuje" });
  });
});

describe("phase trail reduction", () => {
  it("keeps the state of the last event of every phase", () => {
    const trail = phaseTrail([flow(1, "a", "pr.checks", "checks", "fail"), flow(2, "a", "pr.checks", "checks", "ok"),
      flow(3, "a", "pr.review", "review", "wait"), flow(4, "a", "x", "unknown", "ok")]);
    expect(trail).toEqual([null, null, null, "ok", "wait", null, null]);
  });
});

describe("stable order while the pointer is over the map", () => {
  it("keeps rows in place and appends new ones; unfrozen it follows the new order", () => {
    expect(stableOrder(["a", "b"], ["c", "b", "a"], true)).toEqual(["a", "b", "c"]);
    expect(stableOrder(["a", "b"], ["b"], true)).toEqual(["b"]);
    expect(stableOrder(["a", "b"], ["b", "a"], false)).toEqual(["b", "a"]);
  });
});
