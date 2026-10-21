import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import type { PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import { cardTimeline, executionTone } from "./card-timeline";

const head = "a".repeat(40);
const change = (id: string, extra: Partial<PlanChangeset> = {}): PlanChangeset => ({ id, parentRevision: head, subject: id,
  by: { kind: "agent", name: "codex" }, createdAt: `2026-10-2${id.length}T10:00:00Z`, accepted: false,
  changes: [{ nodeId: "task_a" } as PlanChangeset["changes"][number]], ...extra });
const run = (extra: Partial<ExecutionSummary> = {}): ExecutionSummary => ({ executionId: "e".repeat(32), project: "draft", workspace: "draft",
  nodeId: "task_a", epoch: 2, acceptedRevision: head, assignmentDigest: "d", state: "running", serverNow: 100, expiresAt: 160, createdAt: "2026-10-21T10:00:00Z", ...extra });

describe("card timeline", () => {
  it("orders the journey baseline → changes → claim → evidence → PR → writeback", () => {
    const view = cardTimeline({ nodeId: "task_a", state: agentStateFixture(), changesets: [change("b", { accepted: true })], executions: [run()] });
    expect(view.steps.map(item => item.kind)).toEqual(["baseline", "changeset", "claim", "evidence", "pr", "writeback"]);
  });
  it("moves stale proposals into the fork lane and never onto the main track", () => {
    const view = cardTimeline({ nodeId: "task_a", state: agentStateFixture(), changesets: [change("old", { parentRevision: "z".repeat(40) }), change("fresh")], executions: [] });
    expect(view.forks.map(item => item.id)).toEqual(["old"]);
    expect(view.forks[0].attrs).toMatchObject({ "data-oh-stale": "true", "data-oh-parent": "z".repeat(40) });
    expect(view.steps.filter(item => item.kind === "changeset").map(item => item.id)).toEqual(["fresh"]);
  });
  it("ignores changesets and executions of other cards", () => {
    const other = change("x", { changes: [{ nodeId: "task_b" } as PlanChangeset["changes"][number]] });
    const view = cardTimeline({ nodeId: "task_a", state: agentStateFixture(), changesets: [other], executions: [run({ nodeId: "task_b" })] });
    expect(view.steps.some(item => item.id === "x")).toBe(false);
    expect(view.latest).toBeNull();
  });
  it("falls back to the claim action when no run exists", () => {
    const claim = cardTimeline({ nodeId: "task_a", state: agentStateFixture(), changesets: [], executions: [] }).steps.find(item => item.kind === "claim");
    expect(claim).toMatchObject({ tone: "ok", status: "připraveno k převzetí", attrs: { "data-oh-action-id": "act_4" } });
  });
  it("binds the lease attributes and revokes running past the deadline", () => {
    const claim = cardTimeline({ nodeId: "task_a", state: agentStateFixture(), changesets: [], executions: [run()] }).steps.find(item => item.kind === "claim");
    expect(claim?.attrs).toEqual({ "data-oh-execution": "e".repeat(32), "data-oh-epoch": "2", "data-oh-execution-state": "running" });
    expect(executionTone(run(), 59).tone).toBe("ok");
    expect(executionTone(run(), 60)).toEqual({ tone: "bad", status: "po termínu oprávnění" });
    expect(executionTone(run({ state: "reported" })).status).toBe("nahlášeno, neověřeno");
  });
  it("shows the PR link and writeback as gaps while they are not connected", () => {
    const view = cardTimeline({ nodeId: "task_a", state: agentStateFixture(), changesets: [], executions: [run({ state: "reported" })] });
    expect(view.steps.find(item => item.kind === "pr")).toMatchObject({ tone: "gap", status: "nenapojeno" });
    expect(view.steps.find(item => item.kind === "writeback")).toMatchObject({ tone: "gap", attrs: { "data-oh-writeback": "not_connected" } });
    expect(view.steps.find(item => item.kind === "evidence")?.status).toBe("nahlášeno, ne ověřeno");
  });
  it("shows the merged card awaiting human closure (close_card) in the writeback step", () => {
    const close = { id: "act_c", verb: "close_card", method: "POST", path: "/api/desktop-v3/state", targetId: "task_a",
      preconditions: { executionId: "e".repeat(32), mergeSha: "m".repeat(40) }, status: "blocked" as const, blockReason: "human_only" };
    const state = agentStateFixture({ actions: [...agentStateFixture().actions, close] });
    expect(cardTimeline({ nodeId: "task_a", state, changesets: [], executions: [] }).steps.at(-1)).toMatchObject({
      tone: "warn", actor: "human", status: "čeká na uzavření člověkem",
      attrs: { "data-oh-writeback": "awaiting_human_close", "data-oh-action-id": "act_c", "data-oh-merge-sha": "m".repeat(40) } });
    expect(cardTimeline({ nodeId: "task_b", state, changesets: [], executions: [] }).steps.at(-1)?.attrs["data-oh-writeback"]).toBe("not_connected");
  });
  it("marks a missing accepted head as a gap instead of inventing one", () => {
    const state = agentStateFixture({ heads: { ...agentStateFixture().heads, acceptedHead: null } });
    expect(cardTimeline({ nodeId: "task_a", state, changesets: [], executions: [] }).steps[0]).toMatchObject({ tone: "gap", status: "základ chybí" });
  });
});
