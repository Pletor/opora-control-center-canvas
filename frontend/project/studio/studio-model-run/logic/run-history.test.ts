import { describe, expect, it } from "vitest";
import { createSimulation, materializeScenario, stepSimulation } from "../../model/simulation/logic";
import { emptyHistory, HISTORY_TICKS, recordTick } from "./run-history";

describe("run history", () => {
  it("keeps the last 60 ticks per node, edge and summary", () => {
    const model = materializeScenario("web-chain");
    let sim = createSimulation(), history = emptyHistory();
    for (let i = 0; i < HISTORY_TICKS + 5; i++) { sim = stepSimulation(model, sim); history = recordTick(history, sim); }
    expect(history.summary).toHaveLength(HISTORY_TICKS);
    expect(history.summary[0].tick).toBe(6);
    expect(history.nodes.client.at(-1)).toMatchObject({ tick: 65, completed: 250 });
    expect(history.edges["edge-1"]).toHaveLength(HISTORY_TICKS);
  });

  it("drops series of nodes that left the model", () => {
    const model = materializeScenario("web-chain");
    const sim = stepSimulation(model);
    const history = recordTick(emptyHistory(), sim);
    const smaller = { ...model, nodes: model.nodes.filter((n) => n.id !== "db"), edges: model.edges.filter((e) => e.to.nodeId !== "db") };
    const next = recordTick(history, stepSimulation(smaller, sim));
    expect(next.nodes.db).toBeUndefined();
    expect(next.nodes.client).toHaveLength(2);
  });
});
