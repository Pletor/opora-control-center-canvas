import { describe, expect, it } from "vitest";
import { parseCardTrail } from "./card-trail";
import { bundleEvents, commonPrefix, groupByDay, nowLine, plural, runState, runWhen, sourceMark, stepMark, timeline, TRAIL_SETTINGS, whoName } from "./trail-timeline";

const run = (id: string, at: string, state = "reported") => ({ executionId: id, owner: "agent:office", createdAt: at, state, steps: [] });
const event = (at: string, kind: string, label = kind) => ({ at, who: "office", label, kind, source: "det" });

describe("trail-timeline", () => {
  it("slije relace a změny podle času, převzetí a tool.use nekreslí a rozbalí jen nejnovější relaci", () => {
    const trail = parseCardTrail({ nodeId: "n", runs: [run("e2", "2026-10-31T10:42:00Z", "running"), run("e1", "2026-10-30T21:10:00Z", "expired")],
      recent: [event("2026-10-31T11:40:00Z", "step.done"), event("2026-10-31T11:41:00Z", "tool.use", "Edit a.ts"),
        event("2026-10-31T10:42:00Z", "lease.claimed"), event("2026-10-30T09:00:00Z", "task.create")] });
    const items = timeline(trail);
    expect(items.map((item) => item.kind === "run" ? item.run.executionId : item.event.kind)).toEqual(["step.done", "e2", "e1", "task.create"]);
    expect(items.filter((item) => item.kind === "run" && item.expanded).map((item) => item.key)).toEqual(["run:e2"]);
  });

  it("osa má nejvýš limit položek z nastavení aplikace", () => {
    const recent = Array.from({ length: 15 }, (_, i) => event(`2026-10-31T10:${String(10 + i)}:00Z`, "step.done", `s${i} hotovo`));
    expect(timeline(parseCardTrail({ nodeId: "n", recent }))).toHaveLength(TRAIL_SETTINGS.limit);
    const crowded = timeline(parseCardTrail({ nodeId: "n", recent, runs: [run("old", "2026-10-31T08:00:00Z")] }));
    expect(crowded).toHaveLength(TRAIL_SETTINGS.limit);
    expect(crowded[crowded.length - 1]).toMatchObject({ kind: "run", key: "run:old", expanded: true });
    expect(timeline(parseCardTrail({ nodeId: "n", runs: [run("e", "2026-10-31T10:00:00Z")] }), { limit: 5, expand: "none" })[0])
      .toMatchObject({ kind: "run", expanded: false });
  });

  it("dělí osu po dnech", () => {
    const trail = parseCardTrail({ nodeId: "n", recent: [event("2026-10-31T11:00:00", "a"), event("2026-10-31T09:00:00", "b"), event("2026-10-30T09:00:00", "c")] });
    const groups = groupByDay(timeline(trail), new Date("2026-10-31T12:00:00"));
    expect(groups.map((group) => [group.label, group.items.length])).toEqual([["Dnes", 2], ["Včera", 1]]);
  });

  it("řádka teď jen u držené karty a jen z běžící relace", () => {
    const recent = [event("2026-10-31T11:41:00Z", "tool.use", "Edit src/a.ts")];
    expect(nowLine(parseCardTrail({ nodeId: "n", recent }))).toBeNull();
    expect(nowLine(parseCardTrail({ nodeId: "n", recent, now: { owner: "a", since: "2026-10-31T11:00:00Z" } })))
      .toEqual({ text: "Edit src/a.ts", at: "2026-10-31T11:41:00Z" });
    expect(nowLine(parseCardTrail({ nodeId: "n", recent, now: { owner: "a", since: "2026-10-31T11:50:00Z" } }))).toBeNull();
  });

  it("jména, stavy, kroky a původ", () => {
    expect(whoName("heart")).toEqual({ name: "Srdce", kind: "heart" });
    expect(whoName("agent:office-ample")).toEqual({ name: "office-ample", kind: "agent" });
    expect(whoName("")).toEqual({ name: "OPORA", kind: "opora" });
    expect(whoName("opora")).toEqual({ name: "OPORA", kind: "opora" });
    expect(runState("expired")).toEqual({ word: "vypršelo", tone: "bad" });
    expect(runState("nový")).toEqual({ word: "nový", tone: "idle" });
    expect(stepMark("done").glyph).toBe("✓");
    expect(stepMark("failed").tone).toBe("bad");
    expect(stepMark("pending", true).tone).toBe("cur");
    expect(stepMark("pending").glyph).toBe("○");
    expect(sourceMark("heart").glyph).toBe("✦");
    expect(sourceMark("human").glyph).toBe("H");
  });

  it("sbalí opakované události jednoho děje za sebou do jedné řádky s počtem", () => {
    const review = (at: string, verb: string) => ({ at, who: "review", label: `Review pletor/ample#40 (kolo 1) ${verb}`, kind: "pr.review", source: "agent" as const });
    const bundles = bundleEvents([
      { at: "2026-10-31T08:45:33Z", who: "opora", label: "Brána merge se změnila", kind: "gate.changed", source: "det" },
      review("2026-10-31T08:44:50Z", "zveřejněna na GitHubu"), review("2026-10-31T08:44:38Z", "odevzdána"),
      { at: "2026-10-31T08:44:38Z", who: "opora", label: "Kolo review 1", kind: "review.round", source: "det" },
      review("2026-10-31T08:44:09Z", "převzata"), review("2026-10-31T08:43:50Z", "uvolněna"),
      { at: "2026-10-31T08:40:00Z", who: "office", label: "s1 hotovo", kind: "step.done", source: "det" },
      { at: "2026-10-31T08:39:00Z", who: "office", label: "s2 hotovo", kind: "step.done", source: "det" }]);
    expect(bundles.map((b) => [b.event.label, b.count])).toEqual([["Brána merge se změnila", 1], ["Review pletor/ample#40 (kolo 1)", 5],
      ["s1 hotovo", 1], ["s2 hotovo", 1]]);
    expect(bundles[1]).toMatchObject({ from: "2026-10-31T08:43:50Z", parts: ["uvolněna", "převzata", "odevzdána", "zveřejněna na GitHubu"],
      event: { who: "review", at: "2026-10-31T08:44:50Z" } });
    expect(commonPrefix(["a b c", "a b d"])).toBe("a b");
    expect(commonPrefix(["x", "y"])).toBe("");
  });

  it("relace: rozsah času u skončené, jen začátek u běžící; české tvary počtu", () => {
    const base = { executionId: "e", ticketId: null, owner: "a", summary: "", source: "agent" as const, attempts: 1, reported: true, steps: [] };
    expect(runWhen({ ...base, createdAt: "2026-10-31T10:42:00", until: "2026-10-31T12:58:00", state: "reported" })).toBe("10:42–12:58");
    expect(runWhen({ ...base, createdAt: "2026-10-31T10:42:00", until: "2026-10-31T12:58:00", state: "running" })).toBe("10:42");
    expect([plural(1, "krok", "kroky", "kroků"), plural(3, "krok", "kroky", "kroků"), plural(8, "krok", "kroky", "kroků")]).toEqual(["1 krok", "3 kroky", "8 kroků"]);
  });
});
