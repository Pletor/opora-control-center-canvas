import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import { cardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import { workView } from "./work-view";

const NOW = Date.parse("2026-10-28T10:00:00Z");
const fields = { goal: "", non_goals: "", acceptance: "", steps: [
  { id: "s1", order: 1, title: "Model", acceptance: [], dependsOn: [] },
  { id: "s2", order: 2, title: "Formulář", acceptance: [], dependsOn: ["s1"] },
] };
function card(extra: Record<string, unknown>) {
  return cardEntry({ ...agentStateFixture(), cards: [{ nodeId: "c1", stage: "work", health: "ok", reason: "runs_active", executionId: "ex1", ...extra } as never] }, "c1");
}

describe("workView", () => {
  it("bez karty v agent-state: nenapojeno, kroky ze zadání čekají, nikdo nestaví", () => {
    const view = workView(null, fields, false, NOW);
    expect(view.connected).toBe(false);
    expect(view.status.health).toBe("not_connected");
    expect(view.steps?.map(row => `${row.id}:${row.status}`)).toEqual(["s1:current", "s2:waiting"]);
    expect(view.run).toEqual({ holder: null, expired: false, step: null, guards: null });
    expect(view.steps?.map(row => row.word)).toEqual(["na řadě", "čeká"]);
    expect(view.dod.segments[0]).toMatchObject({ key: "steps", detail: "0/2" });
  });

  it("běžící karta: držitel lease, běžící krok s názvem ze zadání, stav kroků z agent-state a nálezy strážců", () => {
    const view = workView(card({
      lease: { holder: "agent:builder-1", expiresAt: "2026-10-28T10:05:00Z", epoch: 3 },
      steps: { total: 2, done: 1, current: "s2", items: [{ id: "s1", status: "done", executionId: "ex1" }] },
      guardFindings: { count: 2, severity: "block" },
    }), fields, false, NOW);
    expect(view.connected).toBe(true);
    expect(view.run).toEqual({ holder: "builder-1", expired: false, step: { id: "s2", title: "Formulář" }, guards: { count: 2, severity: "block", label: "blokuje" } });
    expect(view.steps?.map(row => `${row.id}:${row.status}:${row.word}`)).toEqual(["s1:done:hotovo", "s2:current:běží"]);
    expect(view.dod.segments[0]).toMatchObject({ state: "active", detail: "1/2" });
  });

  it("vypršelá lease se označí, krok bez current se vezme z prvního nehotového", () => {
    const view = workView(card({ lease: { holder: "agent:x", expiresAt: "2026-10-28T09:00:00Z", epoch: 1 } }), fields, false, NOW);
    expect(view.run.expired).toBe(true);
    expect(view.run.step).toEqual({ id: "s1", title: "Model" });
  });

  it("zadání bez kroků dá null; backendové dod má přednost a uzavření člověkem se promítne", () => {
    const view = workView(card({ dod: { done: false, missing: ["human_close"] } }), { goal: "x" }, false, NOW);
    expect(view.steps).toBeNull();
    expect(view.dod.source).toBe("backend");
    expect(view.dod.segments.find(item => item.key === "human_close")?.state).not.toBe("done");
    expect(workView(null, null, true, NOW).dod.segments.find(item => item.key === "human_close")?.state).toBe("done");
  });
});
