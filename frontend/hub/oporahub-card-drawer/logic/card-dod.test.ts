import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { backendDod, dodView } from "./card-dod";
import { cardEntry, nextAction, statusLine } from "./card-header";

function stateWith(card: Record<string, unknown>, actions: AgentState["actions"] = []): AgentState {
  const base = agentStateFixture();
  return { ...base, actions: [...base.actions, ...actions], cards: [{ nodeId: "c1", stage: "work", health: "ok", reason: "runs_active", executionId: "ex1", ...card } as never] };
}
const states = (view: ReturnType<typeof dodView>) => view.segments.map(item => item.state);

describe("definition of done segments", () => {
  it("computes six ordered segments from the card snapshot when the backend has no dod", () => {
    const card = cardEntry(stateWith({ steps: { total: 7, done: 3, current: "s4" }, gate: { status: "blocked", rule: "open_important_findings" } }), "c1");
    const view = dodView({ card, prState: "open" });
    expect(view.source).toBe("computed");
    expect(view.segments.map(item => item.key)).toEqual(["steps", "card_acceptance", "gate_ready", "merged", "plan_written_back", "human_close"]);
    expect(states(view)).toEqual(["active", "unknown", "active", "active", "todo", "todo"]);
    expect(view.segments[0]).toMatchObject({ detail: "3/7", progress: 3 / 7 });
  });
  it("treats merge, write-back and human close as a chain", () => {
    const card = cardEntry(stateWith({ stage: "plan_writeback", reason: "awaiting_human_close", steps: { total: 2, done: 2, current: null } }), "c1");
    expect(states(dodView({ card }))).toEqual(["done", "done", "done", "done", "done", "active"]);
    const closed = dodView({ card, eventKinds: new Set(["card.closed"]) });
    expect(closed.done).toBe(true);
  });
  it("uses process-sync acceptance evidence and human close", () => {
    expect(dodView({ card: null, acceptance: false }).segments[1].state).toBe("todo");
    expect(dodView({ card: null, acceptance: true }).segments[1].state).toBe("done");
    expect(dodView({ card: null, closed: true }).segments.map(item => item.state).slice(1)).toEqual(["done", "done", "done", "done", "done"]);
  });
  it("falls back to step results and marks a card without steps as unknown", () => {
    expect(dodView({ card: null, steps: { total: 2, done: 2 } }).segments[0].state).toBe("done");
    expect(dodView({ card: null }).segments[0]).toMatchObject({ state: "unknown", detail: "bez kroků" });
  });
  it("prefers the backend dod in both wire shapes", () => {
    expect(backendDod({ done: false, missing: ["human_close"] })).toMatchObject({ steps: true, human_close: false });
    expect(backendDod({ steps: true, card_acceptance: true, gate_ready: true, merged: false, plan_written_back: false, human_close: false })).toMatchObject({ merged: false });
    expect(backendDod({ steps: "yes" })).toBeNull();
    const card = cardEntry(stateWith({ dod: { done: false, missing: ["gate_ready", "merged", "plan_written_back", "human_close"] } }), "c1");
    const view = dodView({ card });
    expect(view.source).toBe("backend");
    expect(states(view)).toEqual(["done", "done", "todo", "todo", "todo", "todo"]);
  });
  it("reads the agent-state dod with gate kind", () => {
    const dod = { steps: true, card_acceptance: true, gate_ready: true, merged: true, plan_written_back: false, human_close: false,
      gate: "external", done: false, missing: ["plan_written_back", "human_close"] };
    const view = dodView({ card: cardEntry(stateWith({ dod, steps: { total: 2, done: 2, current: null, items: [] } }), "c1") });
    expect(view).toMatchObject({ source: "backend", gate: "external", done: false });
    expect(states(view)).toEqual(["done", "done", "done", "done", "todo", "todo"]);
    expect(view.segments[2].detail).toBe("GitHub");
  });
});

describe("header status and next action", () => {
  it("reads the status line and is honest without a card", () => {
    expect(statusLine(cardEntry(stateWith({}), "c1"))).toMatchObject({ glyph: "✓", stage: "běh", reasonCode: "runs_active" });
    expect(statusLine(null)).toMatchObject({ health: "not_connected", stage: "—" });
  });
  it("resolves nextActionId and labels the actor", () => {
    const action = { id: "a-close", verb: "close_card", method: "POST", path: "/api/desktop-v3/state", targetId: "c1", preconditions: {},
      status: "blocked" as const, blockReason: "human_only" };
    const state = stateWith({ nextActionId: "a-close" }, [action]);
    expect(nextAction(state, cardEntry(state, "c1"), "c1")).toMatchObject({ label: "Uzavřít kartu", actor: "human", blockText: "rozhoduje člověk" });
  });
  it("falls back to the first action that targets the card or its execution", () => {
    const action = { id: "a-claim", verb: "claim", method: "POST", path: "/api/oporahub/executions/claim", targetId: "c1", preconditions: {}, status: "ready" as const };
    const state = stateWith({}, [action]);
    expect(nextAction(state, cardEntry(state, "c1"), "c1")).toMatchObject({ id: "a-claim", actor: "agent", status: "ready" });
    expect(nextAction(null, null, "c1")).toBeNull();
  });
});
