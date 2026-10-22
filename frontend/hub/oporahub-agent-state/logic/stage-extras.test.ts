import { describe, expect, it } from "vitest";
import { agentStateFixture } from "./fixtures";
import { reviewGate, stageExtra } from "./stage-extras";
import type { AgentState } from "./agent-state";

const withReview = (health: AgentState["stages"][number]["health"], reason: string, gaps = agentStateFixture().gaps) =>
  agentStateFixture({ gaps, stages: agentStateFixture().stages.map(item => item.id === "review" ? { ...item, health, reason } : item) });

describe("review stage → merge gate", () => {
  it("names the gate rule that holds the merge", () => {
    expect(reviewGate(withReview("blocking", "open_security_findings"))).toEqual({ status: "blocked", rule: "open_security_findings" });
    expect(reviewGate(withReview("waiting", "stale_against_main"))).toEqual({ status: "pending", rule: "stale_against_main" });
    expect(stageExtra(withReview("waiting", "template_incomplete"), "review")).toMatchObject({
      tone: "warn", attrs: { "data-oh-gate-status": "pending", "data-oh-gate-rule": "template_incomplete" } });
  });
  it("keeps the generic gate code without inventing a rule", () => {
    expect(reviewGate(withReview("waiting", "review_gate_pending"))).toEqual({ status: "pending", rule: "" });
  });
  it("reports the gate off while AI review is a known gap, clear otherwise", () => {
    expect(reviewGate(withReview("waiting", "human_review_required")).status).toBe("off");
    expect(reviewGate(withReview("ok", "nothing_to_review", [])).status).toBe("clear");
  });
});

describe("proposal stage → auto-rebase conflicts", () => {
  it("counts resolve_conflict actions and opens the conflict drawer", () => {
    const action = { id: "act_r", verb: "proposal.resolve_conflict", method: "POST", path: "/api/oporahub/auto-rebase/conflicts/c1/resolve",
      targetId: "c1", preconditions: {}, status: "ready" as const };
    const state = agentStateFixture({ actions: [...agentStateFixture().actions, action] });
    expect(stageExtra(state, "proposal")).toMatchObject({ attrs: { "data-oh-conflicts": "1" }, target: { kind: "conflicts" } });
    expect(stageExtra(agentStateFixture(), "proposal")).toBeNull();
  });
});
