import { describe, expect, it } from "vitest";
import { emptyBuffer, ingest, pause, resume, visibleStream, workerOptions } from "./stream-buffer";
import { mergeEvents } from "./process-event";
import { flow } from "./fixtures";

describe("stream buffer: pause reading, data keeps arriving", () => {
  it("shows events live, buffers them while paused and releases them on resume", () => {
    let buffer = ingest(emptyBuffer(), [flow(1, "a", "tool.use", "work", "progress")]);
    expect(buffer.shown).toHaveLength(1);
    buffer = ingest(pause(buffer), [flow(1, "a", "tool.use", "work", "progress"), flow(2, "a", "tool.use", "work", "progress"), flow(3, "b", "x", "plan", "ok")]);
    expect(buffer.shown.map((event) => event.id)).toEqual([1]);
    expect(buffer.pending.map((event) => event.id)).toEqual([2, 3]);
    buffer = ingest(buffer, [flow(2, "a", "tool.use", "work", "progress")]);
    expect(buffer.pending).toHaveLength(2);
    buffer = resume(buffer);
    expect(buffer).toMatchObject({ paused: false, pending: [] });
    expect(buffer.shown.map((event) => event.id)).toEqual([1, 2, 3]);
  });
  it("returns the same buffer when nothing is new (no re-render)", () => {
    const buffer = ingest(emptyBuffer(), [flow(1, "a", "x", "work", "ok")]);
    expect(ingest(buffer, [flow(1, "a", "x", "work", "ok")])).toBe(buffer);
  });
});

describe("dedupe by eventId", () => {
  it("drops a redelivered producer event even under a new outbox id", () => {
    const first = flow(5, "a", "tool.use", "work", "progress", { source: "office", eventId: "office:f:77" });
    const again = flow(9, "a", "tool.use", "work", "progress", { source: "office", eventId: "office:f:77" });
    expect(mergeEvents([first], [again, flow(10, "a", "x", "work", "ok")]).map((event) => event.id)).toEqual([5, 10]);
  });
  it("keeps only the newest `keep` events in cursor order", () => {
    expect(mergeEvents([], [flow(3, "a", "x", "work", "ok"), flow(1, "a", "x", "work", "ok"), flow(2, "a", "x", "work", "ok")], 2).map((event) => event.id)).toEqual([2, 3]);
  });
});

describe("stream filter", () => {
  it("filters by card and worker, newest first, and lists workers once", () => {
    const events = [flow(1, "a", "x", "work", "ok", { source: "office", worker: "Ada" }), flow(2, "b", "x", "work", "ok", { source: "office", worker: "Bob" }),
      flow(3, "a", "x", "work", "ok", { source: "office", worker: "Ada" })];
    expect(visibleStream(events, { card: "a", worker: "" }).map((event) => event.id)).toEqual([3, 1]);
    expect(visibleStream(events, { card: "", worker: "w-Bob" }).map((event) => event.id)).toEqual([2]);
    expect(workerOptions(events)).toEqual([{ id: "w-Ada", name: "Ada" }, { id: "w-Bob", name: "Bob" }]);
  });
});
