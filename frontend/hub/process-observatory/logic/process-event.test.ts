import { describe, expect, it } from "vitest";
import { ago, initials, toFlowEvent } from "./process-event";
import { wire } from "./fixtures";
import { sourceChips } from "./source-health";

describe("process event read from the shared events stream", () => {
  it("flattens office fields: source time, worker, refs, tool", () => {
    const raw = wire(7, null, "tool.use", "work", "progress", {
      source: "office", worker: "Ada", tool: { name: "Edit", target: "a.ts" },
      refs: { cardId: "n-42", executionId: "ex-9", branch: "card/x", pr: 31, url: "https://github.com/o/r/pull/31" },
      data: { actor: { kind: "worker", id: "w-3", name: "Ada" }, sourceAt: "2026-10-22T10:14:03.120Z" },
    });
    expect(toFlowEvent(raw)).toMatchObject({ key: "office:floor:7", source: "office", phase: 2, state: "progress", cardId: "n-42",
      workerId: "w-3", workerName: "Ada", executionId: "ex-9", branch: "card/x", pr: 31, at: "2026-10-22T10:14:03.120Z", tool: { name: "Edit" } });
  });
  it("reads an Opora event without process columns as source opora with a fallback key", () => {
    const raw = { ...wire(9, "n-1", "merge.done", "merge", "ok"), source: undefined, eventId: undefined, state: "weird", phase: null };
    expect(toFlowEvent(raw)).toMatchObject({ key: "opora:9", source: "opora", phase: -1, state: "info", cardId: "n-1", workerName: "" });
  });
  it("never takes the producer identity (X-Opora-Actor) of an office or GitHub event for the worker", () => {
    const raw = { ...wire(3, "a", "pr.checks", "checks", "fail", { source: "github" }), actor: { kind: "agent", name: "shot" } };
    expect(toFlowEvent(raw)).toMatchObject({ workerName: "", workerId: "" });
  });
  it("makes worker initials and relative ages", () => {
    expect([initials("Vývojář 1"), initials("ada"), initials("")]).toEqual(["V1", "AD", "—"]);
    expect([ago(0, 1), ago(1000, 13000), ago(0 + 1, 1 + 180_000)]).toEqual(["—", "před 12 s", "před 3 min"]);
  });
});

describe("source health chips", () => {
  it("never claims a source is live without the server saying so", () => {
    expect(sourceChips(null).every((chip) => chip.tone === "gap" && chip.state === "neznámo")).toBe(true);
    const chips = sourceChips({ now: "", officeConnected: false, officeFreshMinutes: 10, listeners: 1,
      sources: { office: { lastAt: "2026-10-22T10:00:00Z", ageSeconds: 900 }, opora: { lastAt: null, ageSeconds: null } },
      memory: { status: "disabled" } });
    expect(chips.map((chip) => [chip.name, chip.state, chip.tone])).toEqual([
      ["Kancelář", "odpojeno", "bad"], ["Opora", "bez událostí", "gap"], ["GitHub", "bez událostí", "gap"], ["OpenViking", "vypnuto", "gap"]]);
  });
});
