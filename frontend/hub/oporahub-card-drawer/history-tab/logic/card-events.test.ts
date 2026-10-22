import { describe, expect, it } from "vitest";
import { eventCategory, eventTitle, eventTone, matchesFilter, parseEventPage, readCardEvents, type EventPage } from "./card-events";

const raw = (id: number, kind: string, nodeId: string | null, extra: Record<string, unknown> = {}) =>
  ({ id, at: "2026-10-22T10:00:00Z", kind, nodeId, executionId: null, stepId: null, prNumber: null, stage: null, health: null,
    actor: { kind: "agent", name: "codex" }, data: {}, ...extra });

describe("card events", () => {
  it("parses a page strictly enough to drop malformed events", () => {
    const page = parseEventPage({ events: [raw(1, "step.done", "c1"), { id: "x" }], cursor: 1, head: 3, gap: false });
    expect(page.events).toHaveLength(1);
    expect(page).toMatchObject({ cursor: 1, head: 3 });
    expect(() => parseEventPage({})).toThrow();
  });
  it("pages by cursor and filters the card on the client, newest first", async () => {
    const pages: Record<number, EventPage> = {
      0: parseEventPage({ events: [raw(1, "lease.claimed", "c1"), raw(2, "step.done", "c2")], cursor: 2, head: 4, gap: false }),
      2: parseEventPage({ events: [raw(3, "step.started", "c1"), raw(4, "pr.linked", "c1")], cursor: 4, head: 4, gap: false }),
    };
    const seen: number[] = [];
    const result = await readCardEvents(async since => { seen.push(since); return pages[since]; }, "c1");
    expect(seen).toEqual([0, 2]);
    expect(result.events.map(item => item.id)).toEqual([4, 3, 1]);
    expect(result).toMatchObject({ head: 4, truncated: false });
  });
  it("stops at the page cap and says so", async () => {
    let calls = 0;
    const result = await readCardEvents(async since => { calls++; return parseEventPage({ events: [raw(since + 1, "x", "c1")], cursor: since + 1, head: 99 }); }, "c1", 3);
    expect(calls).toBe(3);
    expect(result.truncated).toBe(true);
  });
  it("categorises, titles and tones events", () => {
    const [spec, run, review, human] = [raw(1, "changeset.accepted", "c"), raw(2, "step.started", "c", { stepId: "s4" }),
      raw(3, "pr.linked", "c", { prNumber: 145 }), raw(4, "card.closed", "c", { actor: { kind: "human", name: "Martin" } })].map(item => parseEventPage({ events: [item] }).events[0]);
    expect([spec, run, review].map(eventCategory)).toEqual(["spec", "run", "review"]);
    expect(matchesFilter(human, "people")).toBe(true);
    expect(matchesFilter(run, "people")).toBe(false);
    expect(eventTitle(run)).toBe("s4 zahájen");
    expect(eventTitle(review)).toBe("PR #145 propojen");
    expect(eventTitle(parseEventPage({ events: [raw(5, "custom.kind", "c")] }).events[0])).toBe("custom.kind");
    expect(eventTone(human)).toBe("warn");
    expect(eventTone(parseEventPage({ events: [raw(6, "step.failed", "c")] }).events[0])).toBe("bad");
  });
});
