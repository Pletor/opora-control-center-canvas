import { describe, expect, it } from "vitest";
import { createSimulation, materializeScenario, modelCommand, stepSimulation } from "../../model/simulation/logic";
import { cardRuns, linkFlows, runSummary, stateLabel } from "./run-view";

describe("run view", () => {
  it("gives each card its state, three stage numbers and telemetry", () => {
    const model = materializeScenario("web-chain");
    const runs = cardRuns(stepSimulation(model));
    const client = runs.get("client")!;
    expect(client.state).toBe("healthy");
    expect(client.stateLabel).toBe("v pořádku");
    expect(client.stages[0]).toBe("250");
    expect(client.stages[2]).toBe("250");
    expect(client.rps).toBe(250);
    expect(client.failed).toBe(false);
    expect(cardRuns(createSimulation()).size).toBe(0);
  });

  it("marks a crashed card failed and a slow one slow", () => {
    const model = materializeScenario("web-chain");
    let sim = stepSimulation(model);
    modelCommand(sim, model, "crash", ["db"]);
    modelCommand(sim, model, "slow", ["service"]);
    sim = stepSimulation(model, sim);
    const runs = cardRuns(sim);
    expect(runs.get("db")).toMatchObject({ failed: true, stateLabel: "výpadek" });
    expect(runs.get("service")!.slow).toBe(true);
  });

  it("turns edge rows into particle flows with error responses on synchronous links", () => {
    const model = materializeScenario("web-chain");
    let sim = stepSimulation(model);
    expect(linkFlows(sim).get("edge-1")).toMatchObject({ type: "http-request", accepted: 250, errorResponse: 0 });
    modelCommand(sim, model, "crash", ["db"]);
    sim = stepSimulation(model, sim);
    const flows = linkFlows(sim);
    expect([...flows.values()].some((flow) => flow.errorResponse > 0)).toBe(true);
    expect(linkFlows({ ...sim, definitionPending: true }).size).toBe(0);
  });

  it("summarises throughput, error rate and the busiest node", () => {
    const model = materializeScenario("web-chain");
    const healthy = runSummary(stepSimulation(model), model);
    expect(healthy.throughput).toBe(250);
    expect(healthy.errorRate).toBe(0);
    expect(healthy.busiest?.utilization).toBeGreaterThan(0);
    const sim = stepSimulation(model);
    modelCommand(sim, model, "crash", ["service"]);
    const failed = runSummary(stepSimulation(model, sim), model);
    expect(failed.errorRate).toBe(1);
    expect(runSummary(createSimulation(), model)).toMatchObject({ throughput: 0, errorRate: 0, busiest: null });
    expect(stateLabel("unknown")).toBe("unknown");
  });
});
