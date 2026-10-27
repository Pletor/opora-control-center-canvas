import { describe, expect, it } from "vitest";
import { createSimulation, materializeScenario, stepSimulation, validateSimulationModel } from "../../model/simulation/logic";
import { emptyStudioModel } from "../../model/logic/model-types";
import { addNode, type EditModel } from "../../studio-model/logic/model-edit";
import { nodeIncidents, planIncident, unplanIncident } from "./incident-plan";

const plain = (): EditModel => addNode(emptyStudioModel("web"), "service", { x: 0, y: 0 }, "svc").model;
const ok = (result: ReturnType<typeof planIncident>) => { if ("error" in result) throw new Error(result.error); return result.model; };

describe("incident plan", () => {
  it("creates the MODEL definition when the model has none and passes validation", () => {
    const model = ok(planIncident(plain(), "crash", "svc", 3));
    expect(model.modelDefinition).toMatchObject({ version: "flow-model/1", layer: "MODEL", incidents: [{ tick: 3, kind: "crash", nodeIds: ["svc"] }] });
    expect(() => validateSimulationModel(model)).not.toThrow();
  });

  it("merges the same tick and kind and keeps ticks ordered", () => {
    let model = materializeScenario("web-chain");
    model = { ...model, modelDefinition: { ...model.modelDefinition, incidents: [] } };
    model = ok(planIncident(model, "slow", "service", 5)) as typeof model;
    model = ok(planIncident(model, "crash", "db", 2)) as typeof model;
    model = ok(planIncident(model, "slow", "front", 5)) as typeof model;
    model = ok(planIncident(model, "slow", "front", 5)) as typeof model;
    expect(model.modelDefinition.incidents).toEqual([{ tick: 2, kind: "crash", nodeIds: ["db"] }, { tick: 5, kind: "slow", nodeIds: ["service", "front"] }]);
    expect(nodeIncidents(model, "front")).toEqual([{ index: 1, incident: model.modelDefinition.incidents[1] }]);
    const fewer = unplanIncident(model, 0, "db");
    expect(fewer.modelDefinition!.incidents).toHaveLength(1);
  });

  it("rejects tick 0, surge and unknown nodes like the frontend validation", () => {
    expect(planIncident(plain(), "crash", "svc", 0)).toEqual({ error: expect.stringMatching(/od 1/) });
    expect(planIncident(plain(), "crash", "svc", 1.5)).toHaveProperty("error");
    expect(planIncident(plain(), "surge" as never, "svc", 2)).toHaveProperty("error");
    expect(planIncident(plain(), "crash", "nobody", 2)).toHaveProperty("error");
  });

  it("is applied by the engine at its tick", () => {
    let model = materializeScenario("web-chain");
    model = { ...model, modelDefinition: { ...model.modelDefinition, incidents: [] } };
    model = ok(planIncident(model, "crash", "db", 2)) as typeof model;
    const first = stepSimulation(model, createSimulation());
    expect(first.nodes.db.state).not.toBe("failed");
    expect(stepSimulation(model, first).nodes.db.state).toBe("failed");
  });
});
