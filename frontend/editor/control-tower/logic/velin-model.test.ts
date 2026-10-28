import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import type { AgentCardStage } from "@/hub/oporahub-agent-state/logic/agent-state";
import { mapGapsForAgents, velinModel } from "./velin-model";

const node = (id: string, kind: "node" | "sector", parentId: string | null, name = id) => ({ id, parentId, kind, name, purpose: "", x: 0, y: 0 });
const graph: Graph = { edges: [], nodes: [node("s1", "sector", null, "Broker"), node("a", "node", "s1", "Alfa"), node("b", "node", "s1", "Beta"),
  node("c", "node", null, "Gama"), node("d", "node", "s1", "Delta")] };
const card = (nodeId: string, extra: Partial<AgentCardStage>): AgentCardStage =>
  ({ nodeId, stage: "plan", health: "ok", reason: "card_in_plan", executionId: null, ...extra });
const state = agentStateFixture({
  cards: [
    card("s1", { layer: "backend" }),
    card("d", { layer: "backend", topoIndex: 3, stage: "review", health: "waiting", reason: "human_review_required", executionId: "e".repeat(32) }),
    card("b", { layer: "backend", topoIndex: 0, stage: "work", executionId: "f".repeat(32),
      lease: { holder: "agent:codex", expiresAt: "2099-01-01T00:00:00Z", epoch: 1 } }),
    card("a", { layer: "backend", topoIndex: 1, blockedBy: ["b"] }),
    card("c", { layer: "frontend", topoIndex: 2, stage: "plan_writeback", reason: "card_closed" }),
  ],
});

describe("Velín nad agent-state", () => {
  const view = velinModel(graph, state);
  it("vrstva → sektor → pilulky podle topoIndex; sektor sám pilulkou není", () => {
    expect(view.layers.map(layer => layer.label)).toEqual(["Backend", "Frontend"]);
    const broker = view.layers[0].sectors[0];
    expect(broker.name).toBe("Broker");
    expect(broker.pills.map(pill => [pill.name, pill.tone])).toEqual([["Beta", "run"], ["Alfa", "blocked"], ["Delta", "human"]]);
    expect(view.layers[1].sectors[0].name).toBe("Bez sektoru");
    expect(view.total).toMatchObject({ run: 1, blocked: 1, ok: 1, human: 1 });
  });

  it("rozhodnutí se váže na kartu přes běh, Teď běží bere lease", () => {
    expect(view.decisions.find(item => item.id === "dec_2")).toMatchObject({ nodeId: "d", cardName: "Delta" });
    expect(view.running.map(pill => pill.nodeId)).toEqual(["b"]);
    expect(view.next.map(item => item.label)).toContain("Převzít kartu");
  });

  it("filtr Problémy nechá jen blokované a problémové karty, počty vrstvy zůstanou celé", () => {
    const filtered = velinModel(graph, state, "problems");
    expect(filtered.layers[0].sectors[0].pills.map(pill => pill.nodeId)).toEqual(["a"]);
    expect(filtered.layers[0].counts.run).toBe(1);
  });
});

describe("Díry mapy pro agenty", () => {
  const gap = (owner: "agent" | "human") => ({ rule: "section.unrealized", message: "Sekce s nemá žádnou komponentu.", nodeId: "a", owner });
  it("počítá jen díry agentů a pozná ořezaný seznam; starší server bez pole nic neukáže", () => {
    expect(mapGapsForAgents(agentStateFixture({ mapGaps: [gap("agent"), gap("human"), gap("agent")], mapGapsTotal: 3 })))
      .toEqual({ count: 2, more: false });
    expect(mapGapsForAgents(agentStateFixture({ mapGaps: [gap("agent")], mapGapsTotal: 70 }))).toEqual({ count: 1, more: true });
    expect(mapGapsForAgents(agentStateFixture({}))).toBeNull();
  });
});
