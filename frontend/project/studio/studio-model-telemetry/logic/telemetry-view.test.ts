import { describe, expect, it } from "vitest";
import { materializeScenario, modelCommand, stepSimulation } from "../../model/simulation/logic";
import { edgeMetrics, nodeMetrics, sparkPoints, sparkRange } from "./telemetry-view";

describe("telemetry view", () => {
  it("lists node and edge values as model calculations", () => {
    const model = materializeScenario("web-chain");
    let sim = stepSimulation(model);
    expect(nodeMetrics(sim.nodes.client).find((m) => m.label === "Dokončeno")?.value).toBe("250/s");
    expect(edgeMetrics(sim.edges["edge-1"]).find((m) => m.label === "Přijato")?.value).toBe("250/s");
    modelCommand(sim, model, "crash", ["service"]);
    sim = stepSimulation(model, sim);
    expect(nodeMetrics(sim.nodes.service).find((m) => m.label === "Stav")).toMatchObject({ value: "výpadek", alert: true });
    expect(nodeMetrics(undefined)).toEqual([]);
    expect(edgeMetrics(undefined)).toEqual([]);
  });

  it("draws a sparkline scaled from zero to the series maximum", () => {
    expect(sparkPoints([])).toBe("");
    expect(sparkPoints([0, 10], 100, 20)).toBe("4.0,16.0 96.0,4.0");
    expect(sparkPoints([5], 100, 20)).toBe("4.0,4.0");
    expect(sparkRange([1, 9, 3])).toEqual({ last: 3, max: 9 });
  });
});
