import { describe, expect, it } from "vitest";
import type { OporaEvent } from "./events-client";
import { axis, eventText, lanes, markOf } from "./live-model";

const now = Date.parse("2026-10-22T14:30:00Z");
const at = (minutesAgo: number) => new Date(now - minutesAgo * 60_000).toISOString();
const event = (id: number, kind: string, minutesAgo: number, extra: Partial<OporaEvent> = {}): OporaEvent => ({
  id, at: at(minutesAgo), kind, projectId: "p", workspaceId: "w", nodeId: "a", executionId: "e", stepId: null, prNumber: null,
  stage: null, health: null, actor: { kind: "agent", name: "agent:codex-2" }, data: {}, ...extra });

describe("živý proces", () => {
  it("značky, heartbeat a pás pronájmu na dráze karty", () => {
    const events = [event(1, "lease.claimed", 10), event(2, "lease.heartbeat", 5), event(3, "step.done", 4, { stepId: "s3" }), event(4, "gate.changed", 1, { nodeId: "b" })];
    const [lane, other] = lanes(events, [{ nodeId: "a", name: "A", glyph: "▸", leased: true }, { nodeId: "b", name: "B", glyph: "◷", leased: false }], 15 * 60_000, now);
    expect(lane.marks.map((mark) => [mark.glyph, Math.round(mark.x)])).toEqual([["▸", 33], ["✓", 73]]);
    expect(lane.ticks.map(Math.round)).toEqual([67]);
    expect(lane.spans.map((span) => [Math.round(span.from), span.to])).toEqual([[33, 100]]);
    expect(other.marks[0].tab).toBe("review");
  });

  it("pronájem ukončený výsledkem nesahá až do teď", () => {
    const [lane] = lanes([event(1, "lease.claimed", 10), event(2, "result.reported", 5)], [{ nodeId: "a", name: "A", glyph: "", leased: false }], 15 * 60_000, now);
    expect(lane.spans.map((span) => Math.round(span.to))).toEqual([67]);
  });

  it("popisy událostí a neznámý druh doslova", () => {
    expect(eventText(event(1, "step.started", 0, { stepId: "s4" }))).toBe("s4 zahájen");
    expect(eventText(event(1, "gate.changed", 0, { data: { gate: { status: "pending", rule: "required_checks_pending" } } }))).toBe("brána CI běží");
    expect(eventText(event(1, "stage.changed", 0, { stage: "work", data: { reason: "runs_active" } }))).toBe("běh · lease");
    expect(eventText(event(1, "x.unknown", 0))).toBe("x.unknown");
    expect(markOf("review.finding")).toEqual({ glyph: "!", tone: "bad", tab: "review" });
  });

  it("osa po dvou minutách v 15minutovém okně", () => {
    expect(axis(15 * 60_000, now)).toHaveLength(7);
  });
});
