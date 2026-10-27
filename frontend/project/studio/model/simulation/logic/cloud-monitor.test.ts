// Převedeno z prototypu `test/cloud-monitor.test.mjs`; vynecháno: `exportProject`/`importProject` projektu
// (nahrazeno JSON round-tripem modelu přes `validateSimulationModel`).
import { describe, expect, it } from "vitest";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import { validateModelConfig } from "./simulation-config";
import { validateSimulationModel } from "./simulation-validate";

describe("cloud-monitor", () => {
  it("Provider collectors ingest actual graph telemetry, alert on three overloaded steps and restore diagnostic health", () => {
    for (const type of ["aws-cloudwatch", "gcp-monitoring", "aliyun-sls"]) {
      const d = materializeScenario("cloud-monitor-" + type), m = d.nodes.find((n) => n.type === type)!;
      let s = stepSimulation(d), r = s.nodes[m.id];
      expect(r.offered).toBe(2.5);
      expect(r.processed).toBe(1.25);
      expect(r.admitted).toBe(2.5);
      expect(r.technology.retained).toBe(1.25);
      expect(r.outputs["health-out"]).toBe(1);
      expect(r.replicas).toBe(3);
      expect(s.summary!.completed).toBe(250);
      (d.nodes.find((n) => n.type === "service")!.config.model as Record<string, number>).telemetryRate = 1;
      m.config.model = { ingestCapacityRps: 25, replicaCount: 2 };
      s = stepSimulation(d);
      for (let i = 1; i <= 3; i++) {
        r = s.nodes[m.id];
        expect(r.processed).toBe(50);
        expect(r.technology.capacityDropped).toBe(75);
        expect(r.technology.alert).toBe(i === 3);
        if (i < 3) s = stepSimulation(d, s);
      }
      expect(s.events.some((e) => e.kind === "monitor-alert")).toBe(true);
      expect(r.outputs["health-out"]).toBe(0);
      expect(s.summary!.completed).toBe(250);
      const before = structuredClone(s), p = previewSimulation(d, s);
      expect(s).toEqual(before);
      expect(p.nodes[m.id].technology.retained).toBe(r.technology.retained);
      (m.config.model as Record<string, number>).ingestCapacityRps = 1000;
      s = stepSimulation(d, s);
      expect(s.nodes[m.id].technology.alert).toBe(false);
      expect(s.events.some((e) => e.kind === "monitor-clear")).toBe(true);
      expect(s.nodes[m.id].outputs["health-out"]).toBe(1);
      modelCommand(s, d, "crash", [m.id]);
      s = stepSimulation(d, s);
      expect(s.nodes[m.id].processed).toBe(0);
      expect(s.nodes[m.id].outputs["health-out"]).toBe(0);
      expect(s.summary!.completed).toBe(250);
      modelCommand(s, d, "restore-all");
      for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
      expect(s.nodes[m.id].processed).toBe(125);
      const json = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(json))).toEqual(d);
      expect(json.includes('"cohorts":')).toBe(false);
      expect(stepSimulation(d)).toEqual(stepSimulation(d));
    }
  });

  it("Collector integer counts and sampling bounds validate before running", () => {
    for (const config of [{ sampleRate: 2 }, { replicaCount: 0 }, { replicaCount: 1.5 }, { evaluationWindowTicks: 0 }, { activeSeries: .1 }, { cardinalityLimit: -1 }, { retentionMinutes: 1441 }])
      expect(() => validateModelConfig(config)).toThrow();
    validateModelConfig({ retentionMinutes: .5, sampleRate: 0, replicaCount: 1, activeSeries: 0, cardinalityLimit: 0 });
  });

  it("New Service records observed telemetry ratio while saved absent overrides preserve legacy emission", () => {
    const node = createSimulationNode("service");
    expect((node.config.model as Record<string, number>).telemetryRate).toBe(.01);
    const d = materializeScenario("cloud-monitor-aws-cloudwatch"), service = d.nodes.find((n) => n.type === "service")!, monitor = d.nodes.find((n) => n.type === "aws-cloudwatch")!;
    expect(stepSimulation(d).nodes[monitor.id].offered).toBe(2.5);
    delete service.config.model;
    const before = structuredClone(d);
    expect(stepSimulation(d).nodes[monitor.id].offered).toBe(250);
    expect(d).toEqual(before);
    validateModelConfig({ telemetryRate: .01 });
    expect(() => validateModelConfig({ telemetryRate: 1.1 })).toThrow();
  });
});
