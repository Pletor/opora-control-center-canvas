import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import type { AgentAction } from "@/hub/oporahub-agent-state/logic/agent-state";
import { closeCardModel } from "./close-card";

const sha = "0123456789abcdef0123456789abcdef01234567";
function close(over: Partial<AgentAction> = {}, pre: Record<string, unknown> = {}): AgentAction {
  return { id: "act_close", verb: "close_card", method: "POST", path: "/api/desktop-v3/state", targetId: "c1",
    preconditions: { executionId: "ex1", mergeSha: sha, missing: [], gate: "review", ...pre }, status: "ready", ...over };
}
const state = (...actions: AgentAction[]) => agentStateFixture({ actions });

describe("close card after merge", () => {
  it("ready action gives a button with the merge and the human note", () => {
    const model = closeCardModel(state(close()), "c1", { pr: 42 });
    expect(model).toEqual({ state: "ready", label: "Uzavřít kartu", executionId: "ex1", mergeSha: sha, shortSha: "0123456", pr: 42,
      mergeText: "PR #42 · merge 0123456", note: "Uzavřeno po sloučení PR (0123456)" });
  });

  it("closable action waiting on the human (blocked: human_only) is a button too", () => {
    const model = closeCardModel(state(close({ status: "blocked", blockReason: "human_only" })), "c1");
    expect(model).toMatchObject({ state: "ready", mergeText: "merge 0123456", note: "Uzavřeno po sloučení PR (0123456)" });
  });

  it("without mergeSha the note names the PR number", () => {
    expect(closeCardModel(state(close({}, { mergeSha: null })), "c1", { pr: 7 })).toMatchObject({ note: "Uzavřeno po sloučení PR (#7)" });
  });

  it("blocked action gives the reason in Czech and no button", () => {
    const model = closeCardModel(state(close({ status: "blocked", blockReason: "done_state_incomplete" }, { missing: ["steps"] })), "c1");
    expect(model).toEqual({ state: "blocked", blockReason: "done_state_incomplete", missing: ["steps"],
      reason: "Kartu nejde uzavřít: chybí výsledky kroků." });
    expect(model && "label" in model).toBe(false);
  });

  it("lists several missing requirements and falls back to the block label", () => {
    expect(closeCardModel(state(close({ status: "blocked", blockReason: "done_state_incomplete" }, { missing: ["steps", "journeys"] })), "c1"))
      .toMatchObject({ reason: "Kartu nejde uzavřít: chybí výsledky kroků, ověřená cesta zákazníka." });
    expect(closeCardModel(state(close({ status: "blocked", blockReason: "budget_exhausted" })), "c1"))
      .toMatchObject({ reason: "Kartu nejde uzavřít: vyčerpaný rozpočet." });
  });

  it("no action, another card or an already closed card gives nothing", () => {
    expect(closeCardModel(state(), "c1")).toBeNull();
    expect(closeCardModel(null, "c1")).toBeNull();
    expect(closeCardModel(state(close()), "c2")).toBeNull();
    expect(closeCardModel(state(close()), "c1", { closed: true })).toBeNull();
  });
});
