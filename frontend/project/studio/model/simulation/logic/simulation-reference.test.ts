// Determinismus a shoda s prototypem na reprezentativních scénářích (web + DB, fronta + worker, cache-aside, AI gateway,
// breaker s plánovanými incidenty). Referenční hodnoty spočítal prototyp v Node (`04.Architektura-projektu/prototype`,
// `materializeScenario` + 12× `stepSimulation`): souhrn každého kroku `offered,completed,rejected,backlog,maxLatencyMs`
// a po 12. kroku uzel `[state, processed, rejected, backlog, latencyMs, completed]` zaokrouhlený na 6 desetinných míst.
import { describe, expect, it } from "vitest";
import { materializeScenario } from "./scenarios";
import { createSimulation, stepSimulation } from "./simulation";
import type { SimulationState } from "./simulation-types";

const steady = (line: string) => Array(12).fill(line);
const REFERENCE: Record<string, { summaries: string[]; nodes: Record<string, [string, number, number, number, number, number]> }> = {
  "web-chain": {
    summaries: steady("250,250,0,0,12.6"),
    nodes: { client: ["healthy", 250, 0, 0, 12.598425, 250], front: ["healthy", 250, 0, 0, 12.5, 250], service: ["healthy", 250, 0, 0, 12.5, 250], db: ["healthy", 250, 0, 0, 12.5, 250] },
  },
  "queue-backpressure": {
    summaries: Array.from({ length: 12 }, (_, i) => `250,250,0,${150 * (i + 1)},12.5`),
    nodes: { producer: ["healthy", 250, 0, 0, 12.5, 250], queue: ["overloaded", 100, 0, 1800, 12.5, 100], worker: ["healthy", 100, 0, 0, 12.5, 100], db: ["healthy", 100, 0, 0, 12.5, 100] },
  },
  "cloud-cache-aws-elasticache": {
    summaries: steady("250,250,0,0,12.6"),
    nodes: {
      client: ["healthy", 250, 0, 0, 12.598425, 250], lb: ["healthy", 250, 0, 0, 12.5, 250], service: ["healthy", 250, 0, 0, 12.5, 250],
      cache: ["healthy", 250, 0, 0, 1, 250], db: ["healthy", 37.5, 0, 0, 12.5, 37.5],
    },
  },
  "ai-token-budget": {
    summaries: steady("250,250,0,0,135"),
    nodes: {
      client: ["healthy", 250, 0, 0, 12.598425, 250], gate: ["healthy", 250, 0, 0, 12.5, 250], ai: ["healthy", 250, 0, 0, 135, 250],
      search: ["healthy", 187.5, 0, 0, 12.5, 187.5], cache: ["healthy", 250, 0, 0, 12.5, 250], monitor: ["healthy", 250, 0, 0, 12.5, 250],
    },
  },
  "breaker-recovery": {
    summaries: ["250,250,0,0,12.6", "250,250,0,0,12.6", ...Array(9).fill("250,0,250,0,12.6"), "250,1,249,0,12.6"],
    nodes: { client: ["degraded", 250, 0, 0, 12.598425, 1], breaker: ["half-open", 1, 249, 0, 12.5, 1], service: ["healthy", 1, 0, 0, 12.5, 1], db: ["healthy", 1, 0, 0, 12.5, 1] },
  },
};

const r = (n: number) => Math.round(n * 1e6) / 1e6;
function run(id: string): SimulationState[] {
  const model = materializeScenario(id), states: SimulationState[] = [];
  let s = createSimulation();
  for (let t = 0; t < 12; t++) { s = stepSimulation(model, s); states.push(s); }
  return states;
}

describe("simulace: determinismus a referenční hodnoty prototypu", () => {
  for (const [id, expected] of Object.entries(REFERENCE)) {
    it(`${id}: dva běhy dávají stejný stav`, () => {
      expect(run(id)).toEqual(run(id));
    });
    it(`${id}: souhrny a uzly shodné s prototypem`, () => {
      const states = run(id), last = states.at(-1)!;
      expect(states.map((s) => Object.values(s.summary!).join(","))).toEqual(expected.summaries);
      for (const [ref, [state, processed, rejected, backlog, latencyMs, completed]] of Object.entries(expected.nodes)) {
        const row = last.nodes[ref];
        expect([row.state, r(row.processed), r(row.rejected), r(row.backlog), r(row.latencyMs), r(row.completed)], ref).toEqual([state, processed, rejected, backlog, latencyMs, completed]);
      }
    });
  }

  it("materializovaný scénář nese příznak MODEL a plán incidentů", () => {
    const model = materializeScenario("breaker-recovery");
    expect(model.modelDefinition).toMatchObject({ version: "flow-model/1", layer: "MODEL", scenarioId: "breaker-recovery" });
    expect(model.modelDefinition.incidents).toEqual([{ tick: 3, kind: "crash", nodeIds: ["db"] }, { tick: 9, kind: "restore", nodeIds: ["db"] }]);
  });
});
