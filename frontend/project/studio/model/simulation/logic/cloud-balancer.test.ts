// Převedeno z prototypu `test/cloud-balancer.test.mjs`; nic nevynecháno.
import { describe, expect, it } from "vitest";
import { balanceTargets } from "./cloud-profiles";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import type { SimulationState } from "./simulation-types";

const types = ["aws-alb", "gcp-lb", "aliyun-alb"];

describe("cloud-balancer", () => {
  it("Provider balancers split capacity and exclude actively probed failed targets", () => {
    for (const type of types) {
      const d = materializeScenario("cloud-balance-" + type), lb = d.nodes.find((n) => n.type === type)!;
      const [a, b] = d.nodes.filter((n) => n.type === "service");
      let s = stepSimulation(d);
      expect(s.nodes[a.id].offered).toBe(125);
      expect(s.nodes[b.id].offered).toBe(125);
      expect(s.nodes[lb.id].technology.probes).toBe(2);
      expect(s.summary!.completed).toBe(250);
      modelCommand(s, d, "crash", [a.id]);
      s = stepSimulation(d, s);
      expect(s.nodes[a.id].offered).toBe(0);
      expect(s.nodes[b.id].offered).toBe(250);
      expect(s.nodes[lb.id].technology.excluded).toBe(1);
      expect(s.summary!.completed).toBe(250);
      modelCommand(s, d, "restore-all");
      for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
      expect(s.nodes[a.id].offered).toBe(125);
      expect(s.nodes[lb.id].technology.excluded).toBe(0);
      (lb.config.model as Record<string, number>).capacityRps = 100;
      s = stepSimulation(d, s);
      expect(s.nodes[a.id].offered).toBe(50);
      expect(s.nodes[b.id].offered).toBe(50);
      expect(s.summary!.completed).toBe(100);
      const before = structuredClone(s);
      previewSimulation(d, s);
      expect(s).toEqual(before);
    }
  });

  it("Fractional probe budgets carry credit and unknown health is distinct from verified health", () => {
    const targets = [{ edgeId: "a", nodeId: "a", available: false }, { edgeId: "b", nodeId: "b", available: true }], c = { healthProbeRps: .5 };
    let s = balanceTargets(c, targets);
    expect(s.probes).toBe(0);
    expect(s.unknown).toBe(2);
    expect(s.weights.a).toBe(.5);
    s = balanceTargets(c, targets, s);
    expect(s.probes).toBe(1);
    expect(s.health.a).toBe(false);
    expect(s.weights.a).toBe(0);
    expect(s.weights.b).toBe(1);
    const preview = balanceTargets(c, targets, s, true);
    expect(preview.probeCredit).toBe(s.probeCredit);
    expect(preview.probeCursor).toBe(s.probeCursor);
    expect(preview.health).toEqual(s.health);
    const zero = balanceTargets({ healthProbeRps: 0 }, targets);
    expect(zero.unknown).toBe(2);
    expect(zero.weights.a).toBe(.5);
  });

  it("No targets never invent successful work and fixed inputs repeat exactly", () => {
    for (const type of types) {
      const d = materializeScenario("cloud-balance-" + type), lb = d.nodes.find((n) => n.type === type)!;
      let a: SimulationState | undefined, b: SimulationState | undefined;
      for (let i = 0; i < 8; i++) { a = stepSimulation(d, a); b = stepSimulation(d, b); expect(a).toEqual(b); }
      d.edges = d.edges.filter((e) => e.from.nodeId !== lb.id);
      const empty = stepSimulation(d);
      expect(empty.nodes[lb.id].processed).toBe(0);
      expect(empty.summary!.completed).toBe(0);
    }
  });
});
