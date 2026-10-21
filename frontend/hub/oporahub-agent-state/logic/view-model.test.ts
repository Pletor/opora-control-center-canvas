import { describe, expect, it, vi } from "vitest";
import { mirrorJson, parseAgentState, readAgentState } from "./agent-state";
import { agentStateFixture } from "./fixtures";
import { healthGlyph, loopModel, toneOf } from "./loop-model";
import { actionTarget, stripModel } from "./strip-model";
import { actionRows, headFacts } from "./actions-model";

describe("agent-state → přehled (smyčka)", () => {
  const items = loopModel(agentStateFixture());
  const stages = items.flatMap(item => item.kind === "stage" ? [item.stage] : []);
  const connectors = items.flatMap(item => item.kind === "connector" ? [item.connector] : []);
  it("keeps all ten stages in API order, interleaved with connectors", () => {
    expect(stages.map(item => item.n)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(items.map(item => item.kind)).toEqual(Array(10).fill(["stage", "connector"]).flat());
  });
  it("places the snake: 1–5 left to right, 6–10 right to left", () => {
    expect(stages.map(item => [item.row, item.col])).toEqual([[1, 1], [1, 3], [1, 5], [1, 7], [1, 9], [3, 9], [3, 7], [3, 5], [3, 3], [3, 1]]);
    expect(connectors.map(item => item.dir)).toEqual(["right", "right", "right", "right", "down", "left", "left", "left", "left", "up"]);
  });
  it("maps health to tone and a distinct glyph, never colour alone", () => {
    expect(stages.find(item => item.id === "work")).toMatchObject({ tone: "bad", health: "blocking", reasonText: "Běh je po termínu oprávnění." });
    expect(new Set(Object.values(healthGlyph)).size).toBe(4);
    expect(toneOf.not_connected).toBe("gap");
  });
  it("shows unknown reason codes verbatim instead of inventing text", () => {
    expect(stages[1].reasonText).toBe("x_unknown");
  });
  it("marks human steps and agent steps separately", () => {
    expect(stages.filter(item => item.actor === "human").map(item => item.id)).toEqual(["acceptance", "review", "merge"]);
    expect(stages.filter(item => item.actor === "agent").map(item => item.id)).toEqual(["claim", "work", "evidence", "pull_request"]);
  });
  it("breaks connectors touching a not_connected stage and warns before waiting/blocking", () => {
    expect(connectors.find(item => item.from === "review")).toMatchObject({ tone: "broken", label: "revize + SHA · nenapojeno" });
    expect(connectors.find(item => item.from === "plan_writeback")).toMatchObject({ to: "plan", tone: "broken" });
    expect(connectors.find(item => item.from === "claim")?.tone).toBe("warn");
  });
});

describe("agent-state → horní pás", () => {
  it("computes risk percentages, stale count and short head", () => {
    const strip = stripModel(agentStateFixture());
    expect(strip.risk).toMatchObject({ total: 4, pct: { low: 50, elevated: 25, critical: 25 } });
    expect(strip.staleCount).toBe(1);
    expect(strip.headShort).toBe("a".repeat(12));
  });
  it("routes decisions to the exact proposal or execution via their action path", () => {
    const [critical, review] = stripModel(agentStateFixture()).decisions;
    expect(critical).toMatchObject({ kindLabel: "kritické", tone: "bad", target: { kind: "graph", id: "cs1" } });
    expect(review.target).toMatchObject({ kind: "executions", id: "e".repeat(32) });
  });
  it("never lists more than three decisions and handles a missing head", () => {
    const state = agentStateFixture({ heads: { ...agentStateFixture().heads, acceptedHead: null } });
    expect(stripModel(state).headShort).toBe("nezaložena");
    expect(actionTarget({ path: "/api/oporahub/changesets/x/rebase", targetId: "x" }, "t")).toEqual({ kind: "changes", id: "x", title: "t" });
    expect(actionTarget({ path: "/api/oporahub/executions/claim", targetId: "task_a" }, "t").kind).toBe("card");
  });
  it("routes a close_card decision to the card detail, labelled as a human closure", () => {
    const close = { id: "act_c", verb: "close_card", method: "POST", path: "/api/desktop-v3/state", targetId: "task_a",
      preconditions: { executionId: "e".repeat(32), mergeSha: "m".repeat(40) }, status: "blocked" as const, blockReason: "human_only" };
    const state = agentStateFixture({ actions: [...agentStateFixture().actions, close],
      decisions: [{ id: "dec_c", kind: "close_card", targetId: "task_a", title: "Uzavřít kartu po merge PR: A", actionId: "act_c" }] });
    expect(stripModel(state).decisions[0]).toMatchObject({ kindLabel: "uzavření", button: "Uzavřít kartu", target: { kind: "card", id: "task_a" } });
    expect(actionRows(state).at(-1)).toMatchObject({ verbLabel: "Uzavřít kartu", human: true });
  });
  it("counts an empty risk mix as zero percent", () => {
    expect(stripModel(agentStateFixture({ riskMix: { low: 0, elevated: 0, critical: 0 } })).risk.pct).toEqual({ low: 0, elevated: 0, critical: 0 });
  });
});

describe("agent-state → pohled pro agenty", () => {
  it("keeps API order and exact precondition values (null stays null)", () => {
    const rows = actionRows(agentStateFixture());
    expect(rows.map(item => item.id)).toEqual(["act_1", "act_3", "act_4", "act_2"]);
    expect(rows[2].preconditions).toContainEqual({ key: "previousExecutionId", value: "null" });
    expect(rows[2].budget).toBe("2 pokusů · 1 oprav");
    expect(rows[0]).toMatchObject({ statusLabel: "blocked:human_only", human: true });
  });
  it("lists CAS heads including per-card budget policy", () => {
    expect(headFacts(agentStateFixture()).map(item => item.field)).toEqual(["acceptedHead", "graphDigest", "contextVersion", "workingDiffers", "budgetPolicyHead"]);
  });
});

describe("parse, conditional read and DOM mirror", () => {
  it("rejects another scope, a missing stage or unknown health", () => {
    const raw = JSON.parse(JSON.stringify(agentStateFixture()));
    expect(() => parseAgentState(raw, "draft", "other")).toThrow("jinému prostoru");
    expect(() => parseAgentState({ ...raw, stages: raw.stages.slice(1) }, "draft", "draft")).toThrow("smyčku");
    expect(() => parseAgentState({ ...raw, stages: raw.stages.map((item: object) => ({ ...item, health: "green" })) }, "draft", "draft")).toThrow();
    expect(parseAgentState(raw, "draft", "draft").stages).toHaveLength(10);
  });
  it("sends If-None-Match and treats 304 as unchanged", async () => {
    const transport = vi.fn().mockResolvedValue(new Response(null, { status: 304 }));
    await expect(readAgentState("draft", "draft", '"tag"', new AbortController().signal, transport)).resolves.toEqual({ kind: "unchanged" });
    expect(transport.mock.calls[0][1].headers).toEqual({ "If-None-Match": '"tag"' });
  });
  it("returns the fresh document with its ETag", async () => {
    const body = JSON.stringify(agentStateFixture());
    const transport = vi.fn().mockResolvedValue(new Response(body, { status: 200, headers: { ETag: '"v2"' } }));
    const result = await readAgentState("draft", "draft", "", new AbortController().signal, transport);
    expect(result).toMatchObject({ kind: "fresh", etag: '"v2"' });
    expect(transport.mock.calls[0][1].headers).toEqual({});
  });
  it("escapes the mirror so state text cannot close the script element", () => {
    const state = agentStateFixture({ decisions: [{ id: "d", kind: "accept_low", targetId: null, title: "</script><b>", actionId: "a" }] });
    expect(mirrorJson(state)).not.toContain("</script>");
    expect(JSON.parse(mirrorJson(state)).decisions[0].title).toBe("</script><b>");
  });
});
