import { describe, expect, it } from "vitest";
import { buildLanes } from "../../logic/lanes";
import { flow } from "../../logic/fixtures";
import { checksOf, refsOf, turnOf } from "./inspector-model";

const lane = (...events: ReturnType<typeof flow>[]) => buildLanes([], events, { names: {}, officeConnected: true })[0];

describe("card inspector model", () => {
  it("hands the turn to the human when the newest event waits for them", () => {
    expect(turnOf(lane(flow(1, "a", "needs.input", "plan", "blocked", { title: "Který prostor?" })))).toEqual(
      { label: "Čeká na člověka", who: "Vy", what: "Který prostor?", human: true });
    expect(turnOf(lane(flow(1, "a", "tool.use", "work", "progress", { source: "office", worker: "Ada" })))).toMatchObject({ label: "Na tahu", who: "Ada", human: false });
  });
  it("takes refs from the newest event that carries them and links PRs only to https pull URLs", () => {
    const refs = refsOf(lane(flow(1, "a", "run.claim", "work", "start", { executionId: "ex-1", refs: { cardId: "a", branch: "card/a" } }),
      flow(2, "a", "pr.opened", "review", "ok", { prNumber: 31, refs: { cardId: "a", url: "https://github.com/o/r/pull/31", sha: "4be21d0aaaaaaaaaa" } })));
    expect(refs).toEqual({ run: "ex-1", branch: "card/a", pr: "#31", prUrl: "https://github.com/o/r/pull/31", sha: "4be21d0aaaaa", floor: "—" });
    expect(refsOf(lane(flow(1, "a", "pr.opened", "review", "ok", { refs: { cardId: "a", url: "javascript:alert(1)" } }))).prUrl).toBe("");
  });
  it("lists checks once per name, newest result", () => {
    const checks = checksOf(lane(flow(1, "a", "check.self", "checks", "fail", { tool: { name: "test", target: "npm test" } }),
      flow(2, "a", "check.self", "checks", "ok", { tool: { name: "test", target: "npm test" } }), flow(3, "a", "pr.checks", "checks", "wait")));
    expect(checks.map((check) => [check.name, check.state])).toEqual([["pr.checks", "wait"], ["npm test", "ok"]]);
  });
});
