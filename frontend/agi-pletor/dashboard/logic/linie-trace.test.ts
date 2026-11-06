import { describe, expect, it } from "vitest";
import { statusLabel, traceView } from "./linie-trace";

const full = {
  mark: "OP-3F9A1C",
  ticket: { ticketId: "tk_1", state: "open", stateLabel: "otevřeno", body: { essence: "E\nx", build: "B", doneCriteria: ["a"] }, work: { branch: "feat/x" } },
  card: { id: "hero", name: "Hero", link: "/?node=hero", known: true }, revision: "2",
  plan: [{ id: "s2", order: 2, title: "B" }, { id: "s1", order: 1, title: "A", acceptance: "ok" }],
  runs: [{ runId: "run_1", agent: "terminal", startedAt: "t", fromSha: "abcdef0123", status: "verified" }],
  commits: [{ sha: "2522dc84aa", sha7: "2522dc8", title: "fix", runId: null, status: "bogus" }],
  code: [{ path: "a.py", line: 12, symbol: "f", step: 3, status: "verified" }],
  pr: { number: 12, state: "OPEN", url: "u" }, checks: [{ name: "npm test", status: "green", sha: "2522dc84aa" }],
  acceptance: { sha: "2522dc84aa", note: "ok" }, merged: { sha: "abcdef0123", target: "main", at: "t" }, preview: { url: "http://x", state: "running" },
  gaps: [{ kind: "no_card", text: "bez karty" }], sentence: "věta",
};

describe("traceView", () => {
  it("plný JSON", () => {
    const v = traceView(full);
    expect(v.mark).toBe("OP-3F9A1C");
    expect(v.ticket).toMatchObject({ title: "E", doneCriteria: ["a"], branch: "feat/x" });
    expect(v.plan.map((s) => s.id)).toEqual(["s1", "s2"]);
    expect(v.runs[0]).toMatchObject({ fromSha7: "abcdef0", status: "verified" });
    expect(v.commits[0]).toMatchObject({ sha7: "2522dc8", runId: "", status: "inferred" });
    expect(v.code[0]).toMatchObject({ path: "a.py", line: "12", step: "3", status: "verified" });
    expect(v.pr?.number).toBe("12");
    expect(v.checks[0]).toEqual({ name: "npm test", status: "green", sha7: "2522dc8" });
    expect(v.merged?.sha7).toBe("abcdef0");
    expect(v.gaps).toEqual(["bez karty"]);
    expect(v.sentence).toBe("věta");
  });
  it("prázdné vstupy nespadnou", () => {
    for (const raw of [{}, null]) {
      const v = traceView(raw);
      expect(v).toMatchObject({ mark: "", ticket: null, card: null, pr: null, acceptance: null, merged: null, preview: null, sentence: "" });
      expect([v.plan, v.runs, v.commits, v.code, v.checks, v.gaps]).toEqual([[], [], [], [], [], []]);
    }
  });
  it("štítky stavů", () => {
    expect(["verified", "claimed", "inferred", "missing"].map((s) => statusLabel(s as never))).toEqual(["ověřeno", "tvrzeno", "odvozeno", "chybí"]);
  });
});
