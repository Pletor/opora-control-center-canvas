// Převedeno z prototypu `test/client-window.test.mjs`; vynecháno: nic. `removeNode` z S4 vrací nový model (prototyp mutoval doménu).
import { describe, expect, it } from "vitest";
import { removeNode } from "../../logic/model-rules";
import { clientWindow } from "./client-policy";
import { materializeScenario } from "./scenarios";
import { modelCommand, rebaseSimulation, stepSimulation } from "./simulation";

const model = (node: { config: Record<string, unknown> }) => node.config.model as Record<string, any>;

describe("client-window", () => {
  it("Client reprodukuje naměřenou referenční matici čekání a slow badge", () => {
    const matrix: [number, number, number, number, number, string][] = [
      [400, 3000, 250, 12.6, 1, "healthy"], [1, 3000, 80, 3000, 240, "degraded"], [2, 3000, 160, 3000, 240, "degraded"], [3, 3000, 240, 3000, 240, "degraded"],
      [4, 3000, 250, 57.1, 5, "pressured"], [1, 500, 80, 500, 40, "degraded"], [1, 50, 80, 50, 4, "degraded"],
    ];
    for (const [slots, deadline, completed, latency, slow, state] of matrix) {
      const domain = materializeScenario("web-chain"), client = domain.nodes.find((n) => n.type === "client")!;
      Object.assign(model(client), { concurrency: slots, deadlineMs: deadline });
      const frame = stepSimulation(domain), row = frame.nodes[client.id];
      expect(frame.summary!.completed).toBe(completed); expect(Math.round(row.latencyMs * 10) / 10).toBe(latency);
      expect(row.slowFactor).toBe(slow); expect(row.state).toBe(state); expect(row.limited).toBe(250 - completed);
    }
  });
  it("Úprava konfigurace zachová tick, historii i ruční incident a odstraní jen osiřelé identity", () => {
    let domain = materializeScenario("web-chain");
    const db = domain.nodes.find((n) => n.type === "postgresql")!, oldDefinition = structuredClone(domain);
    let state = stepSimulation(domain);
    modelCommand(state, domain, "crash", [db.id]);
    state = stepSimulation(domain, state);
    const before = structuredClone(state);
    model(domain.nodes[0]).concurrency = 1;
    const rebased = rebaseSimulation(domain, state, oldDefinition);
    expect(state).toEqual(before); expect(rebased.tick).toBe(2); expect(rebased.events).toEqual(state.events); expect(rebased.samples).toEqual(state.samples);
    expect(rebased.incidents[db.id].kind).toBe("crash"); expect(rebased.definitionPending).toBe(true);
    const next = stepSimulation(domain, rebased);
    expect(next.tick).toBe(3); expect(next.definitionPending).toBe(false); expect(next.nodes[db.id].state).toBe("failed");
    const previous = structuredClone(domain);
    domain = removeNode(domain, db.id) as typeof domain;
    const removed = rebaseSimulation(domain, next, previous);
    expect(db.id in removed.nodes).toBe(false); expect(db.id in removed.incidents).toBe(false);
    for (const edge of previous.edges.filter((e) => e.to.nodeId === db.id)) expect(edge.id in removed.edges).toBe(false);
  });
  it("Zvýšení souběžnosti zachová historii a zotaví klienta při pokračujícím výstupu", () => {
    const domain = materializeScenario("web-chain"), client = domain.nodes.find((n) => n.type === "client")!;
    model(client).concurrency = 1;
    let state = stepSimulation(domain);
    const old = structuredClone(domain);
    model(client).concurrency = 400;
    state = rebaseSimulation(domain, state, old);
    expect(state.tick).toBe(1);
    state = stepSimulation(domain, state);
    expect(state.summary!.completed).toBe(250); expect(state.nodes[client.id].state).toBe("recovering"); expect(state.nodes[client.id].flowRecoveryProgress).toBe(1);
    state = stepSimulation(domain, state);
    expect(state.nodes[client.id].state).toBe("healthy"); expect(state.summary!.completed).toBe(250); expect(state.samples.length).toBe(3);
  });
  it("Nulový vstup, nulová kapacita a krátký deadline nezpůsobí neplatné numerické výsledky", () => {
    for (const offered of [0, 1, 100000]) for (const capacity of [0, 1, 100000]) {
      const row = clientWindow({ offered, processed: Math.min(offered, capacity), completed: Math.min(offered, capacity), capacity, baselineMs: 12.5, deadlineMs: 5 });
      expect(Number.isFinite(row.latencyMs)).toBe(true); expect(row.latencyMs).toBeGreaterThan(0); expect(row.latencyMs).toBeLessThanOrEqual(5); expect(Number.isFinite(row.limited)).toBe(true);
    }
  });
});
