import { describe, expect, it, vi } from "vitest";
import { mirrorJson, parseAgentState, readAgentState } from "./agent-state";
import { agentStateFixture } from "./fixtures";
import { healthGlyph, reasonText } from "./health-labels";
import { actionTarget } from "./action-target";
import { actionRows, headFacts } from "./actions-model";

describe("health labels and action targets", () => {
  it("gives every health its own glyph, never colour alone", () => {
    expect(new Set(Object.values(healthGlyph)).size).toBe(4);
  });
  it("names known reasons and leaves unknown codes to be shown verbatim", () => {
    expect(reasonText.lease_past_deadline).toBe("Běh je po termínu oprávnění.");
    expect(reasonText.x_unknown).toBeUndefined();
  });
  it("routes actions to the exact proposal, execution or card via their path", () => {
    expect(actionTarget({ path: "/api/oporahub/changesets/x/rebase", targetId: "x" }, "t")).toEqual({ kind: "changes", id: "x", title: "t" });
    expect(actionTarget({ path: "/api/oporahub/executions/claim", targetId: "task_a" }, "t").kind).toBe("card");
    expect(actionTarget({ path: "/api/desktop-v3/state", targetId: "task_a" }, "t")).toMatchObject({ kind: "card", id: "task_a" });
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
