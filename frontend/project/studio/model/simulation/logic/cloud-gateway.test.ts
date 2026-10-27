// Převedeno z prototypu `test/cloud-gateway.test.mjs`; vynecháno: `exportProject`/`importProject` projektu
// (nahrazeno JSON round-tripem modelu přes `validateSimulationModel`).
import { describe, expect, it } from "vitest";
import { connect } from "../../logic/model-rules";
import { cloudConfig } from "./cloud-profiles";
import { gatewayAdmission } from "./gateway-model";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import { validateModelConfig } from "./simulation-config";
import { validateSimulationModel } from "./simulation-validate";

const defaults = () => ({ ...cloudConfig("aws-api-gateway")!, rateLimitRps: 100, burstCapacity: 50, limiterScope: "global", crashAfterTicks: 0 });
type Cfg = Record<string, any>;

describe("cloud-gateway", () => {
  it("Token reserve drains under sustained load, refills while idle and preview repeats the same committed decision", () => {
    const c = defaults();
    let old: Cfg | undefined;
    const values: number[] = [];
    for (let i = 0; i < 4; i++) {
      old = gatewayAdmission(c, 120, old);
      values.push(old.accepted);
      expect(gatewayAdmission(c, 120, old, true).accepted).toBe(old.accepted);
    }
    expect(values).toEqual([120, 120, 110, 100]);
    old = gatewayAdmission(c, 0, old);
    expect(old.tokens).toBe(50);
    expect(gatewayAdmission(c, 150, old).accepted).toBe(150);
  });

  it("Two-step rolling quota, keyed hot traffic and state outage policy have deterministic independent effects", () => {
    const c = { ...defaults(), burstCapacity: 0, limiterAlgorithm: "sliding-window" };
    let old: Cfg | undefined;
    const values: number[] = [];
    for (let i = 0; i < 4; i++) { old = gatewayAdmission(c, 150, old); values.push(old.accepted); }
    expect(values).toEqual([150, 50, 150, 50]);
    const keyed = { ...defaults(), burstCapacity: 0, limiterScope: "keyed", limiterKeyCount: 10, hotKeyShare: .5 };
    const r = gatewayAdmission(keyed, 100);
    expect(r.accepted).toBe(55);
    expect(r.rejected).toBe(45);
    expect(r.logicalKeys).toBe(10);
    expect(gatewayAdmission({ ...keyed, limiterShardCount: 1 }, 100).maxShardLoad).toBe(100);
    expect(Math.abs(gatewayAdmission({ ...keyed, limiterShardCount: 10 }, 100).maxShardLoad - 55)).toBeLessThan(1e-9);
    expect(gatewayAdmission({ ...keyed, stateFailureRate: 1, outagePolicy: "fail-open" }, 100).accepted).toBe(100);
    expect(gatewayAdmission({ ...keyed, stateFailureRate: 1, outagePolicy: "fail-closed" }, 100).accepted).toBe(0);
    expect(gatewayAdmission({ ...keyed, stateFailureRate: .5, outagePolicy: "fail-open" }, 100).bypassed).toBe(50);
  });

  it("All provider gateway graphs apply actual configured admission, direct deadlines, cache failure and recovery", () => {
    for (const type of ["aws-api-gateway", "gcp-api-gateway", "aliyun-api-gateway"]) {
      const d = materializeScenario("cloud-gateway-" + type), g = d.nodes.find((n) => n.type === type)!, service = d.nodes.find((n) => n.type === "service")!;
      const gm = () => g.config.model as Cfg;
      g.config.model = { rateLimitRps: 100, burstCapacity: 0, limiterScope: "global", limiterAlgorithm: "token-bucket", timeoutMs: 60000, crashAfterTicks: 0 };
      let s = stepSimulation(d);
      expect(s.nodes[g.id].processed).toBe(100);
      expect(s.summary!.completed).toBe(100);
      const before = structuredClone(s), preview = previewSimulation(d, s);
      expect(s).toEqual(before);
      expect(preview.nodes[g.id].processed).toBe(100);
      gm().timeoutMs = 1;
      s = stepSimulation(d, s);
      expect(s.summary!.completed).toBe(0);
      expect(s.nodes[g.id].technology.timedOut).toBe(100);
      expect(s.events.some((e) => e.kind === "gateway-timeout")).toBe(true);
      gm().timeoutMs = 60000;
      const cache = createSimulationNode("redis");
      d.nodes.push(cache);
      d.edges.push(connect(d, { nodeId: g.id, portId: "cache-out" }, { nodeId: cache.id, portId: "cache-in" }).edge);
      gm().outagePolicy = "fail-closed";
      modelCommand(s, d, "crash", [cache.id]);
      s = stepSimulation(d, s);
      expect(s.nodes[g.id].processed).toBe(0);
      expect(s.nodes[g.id].technology.stateLinkUnavailable).toBe(true);
      gm().outagePolicy = "fail-open";
      s = stepSimulation(d, s);
      expect(s.nodes[g.id].processed).toBe(250);
      modelCommand(s, d, "restore-all");
      for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
      expect(s.nodes[g.id].processed).toBe(100);
      const text = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(text))).toEqual(d);
      expect(text.includes("stateLinkUnavailable")).toBe(false);
      (service.config.model as Cfg).latencyMs = 500;
      expect(stepSimulation(d)).toEqual(stepSimulation(d));
    }
  });

  it("Gateway string choices and integer keys reject unsupported values instead of coercing them", () => {
    validateModelConfig({ limiterAlgorithm: "token-bucket", limiterScope: "keyed", outagePolicy: "fail-closed", limiterKeyCount: 10 });
    for (const p of [{ limiterAlgorithm: "random" }, { limiterScope: "anything" }, { outagePolicy: 1 }, { limiterKeyCount: 1.5 }, { limiterShardCount: 0 }])
      expect(() => validateModelConfig(p)).toThrow();
  });
});
