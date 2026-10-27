// Převedeno z prototypu `test/pod-resilience.test.mjs`; vynecháno: nic (export/import projektu nahrazen JSON round-tripem modelu).
import { describe, expect, it } from "vitest";
import type { StudioModelNode } from "../../logic/model-types";
import { controllerCommand, controllerFaults, podHealth, podResilienceDefaults, validateDeployment } from "./deployment";
import { simulationDomain } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import type { DeploymentDefinition } from "./simulation-types";
import { validateSimulationModel } from "./simulation-validate";

const model = (n: { config: Record<string, unknown> }) => n.config.model as Record<string, any>;

/** Deployment je uzel enginu (s `deployment` přímo na uzlu); `config` a definice sdílí s modelem. */
function fixture() {
  const d = materializeScenario("deployment-scaling");
  const deployment = simulationDomain(d).nodes.find((n) => n.type === "kubernetes-deployment")!;
  const client = d.nodes.find((n) => n.type === "client")!;
  const def = deployment.deployment as Record<string, any>;
  def.maxReplicas = 2; def.podCapacity = 300; def.replacementTicks = 99;
  model(deployment).crashAfterTicks = 99;
  model(client).rate = 3000;
  return { d, deployment, client, def };
}

describe("pod-resilience", () => {
  it("Observed Pod matrix: unavailable diagnostic at500%, ready dispatch persists, low load recovers0/2→1/2→healthy", () => {
    const c = { ...podResilienceDefaults, crashThresholdPct: 100, crashAfterTicks: 1 };
    const high = podHealth(c, {}, 1500, 300, 8, false);
    expect(high.state).toBe("unavailable");
    expect(high.latencyMs).toBe(8000);
    expect(high.slowFactor).toBe(1000);
    const low = podHealth(c, high, 50, 300, 8, false);
    expect(low.state).toBe("recovering");
    expect(low.recoveryProgress).toBe(0);
    expect(low.latencyMs).toBe(9.6);
    const one = podHealth(c, low, 50, 300, 8, true);
    expect(one.state).toBe("recovering");
    expect(one.recoveryProgress).toBe(1);
    expect(podHealth(c, one, 50, 300, 8, true).state).toBe("healthy");
  });

  it("Sustained diagnostic thresholds use clocked evaluations; previews do not advance counters", () => {
    const c = { ...podResilienceDefaults };
    let h = podHealth(c, {}, 1500, 300, 8, true);
    expect(h.overloadTicks).toBe(1);
    const before = structuredClone(h);
    for (let i = 0; i < 20; i++) {
      const preview = podHealth(c, h, 1500, 300, 8, false);
      expect(preview.overloadTicks).toBe(1);
      expect(preview.unavailable).toBe(false);
    }
    expect(h).toEqual(before);
    h = podHealth(c, h, 1500, 300, 8, true);
    expect(h.unavailable).toBe(false);
    h = podHealth(c, h, 1500, 300, 8, true);
    expect(h.unavailable).toBe(true);
    expect(h.overloadTicks).toBe(3);
  });

  it("Readiness, diagnostic unavailable and parent SQL are separate actual model outputs", () => {
    const { d, deployment, client, def } = fixture();
    Object.assign(def.podResilience, { crashThresholdPct: 100, crashAfterTicks: 1 });
    let s = stepSimulation(d), c = s.controllers![deployment.id];
    expect(c.ready).toBe(2);
    expect(c.instances.every((p: any) => p.readiness === "ready" && p.state === "unavailable")).toBe(true);
    expect(c.processed).toBe(600);
    expect(s.edges[d.edges.find((e) => e.from.nodeId === deployment.id)!.id].offered).toBe(600);
    const crashed = c.instances[0].id;
    s.controllers![deployment.id] = controllerCommand(deployment, c, "crash", crashed);
    s = stepSimulation(d, s);
    c = s.controllers![deployment.id];
    expect(c.ready).toBe(1);
    expect(c.instances.find((p: any) => p.id === crashed).processed).toBe(0);
    expect(c.instances.find((p: any) => p.id === crashed).readiness).toBe("unavailable");
    model(client).rate = 100;
    const preview = previewSimulation(d, s);
    expect(preview.controllers![deployment.id].instances.find((p: any) => p.id !== crashed).health.state).toBe("recovering");
  });

  it("Shared stress/degraded/recovery settings and latency ceiling have observable effects", () => {
    const c = { ...podResilienceDefaults, stressThresholdPct: 30, degradedThresholdPct: 60, recoveryThresholdPct: 20, latencyCeilingMs: 1000 };
    let h = podHealth(c, {}, 125, 300, 8, false);
    expect(h.state).toBe("pressured");
    expect(podHealth(c, {}, 200, 300, 8, false).state).toBe("degraded");
    h = podHealth(c, h, 80, 300, 8, true);
    expect(h.state).toBe("recovering");
    expect(h.recoveryProgress).toBe(0);
    expect(podHealth(c, {}, 1500, 300, 8, false).latencyMs).toBe(1000);
    const { d, deployment, def } = fixture();
    Object.assign(def.podResilience, c);
    const frame = previewSimulation(d);
    expect(frame.controllers![deployment.id].instances.every((p: any) => p.latencyMs === 1000)).toBe(true);
  });

  it("Parent output override persists and overrides local per-instance contribution only when processing", () => {
    const { d, deployment, def } = fixture();
    def.outputOverrides["sql-out"] = 500;
    const saved = JSON.stringify(d);
    let s = stepSimulation(d);
    const edge = d.edges.find((e) => e.from.nodeId === deployment.id)!;
    expect(s.edges[edge.id].offered).toBe(500);
    expect(validateSimulationModel(JSON.parse(saved))).toEqual(d);
    expect(saved.includes("instances")).toBe(false);
    s.controllers![deployment.id].instances[0].overrides["sql-out"] = 123;
    s = stepSimulation(d, s);
    expect(s.edges[edge.id].offered).toBe(500);
    for (const instance of s.controllers![deployment.id].instances)
      s.controllers![deployment.id] = controllerCommand(deployment, s.controllers![deployment.id], "crash", instance.id);
    s = stepSimulation(d, s);
    expect(s.edges[edge.id].offered).toBe(0);
  });

  it("Legacy definitions do not silently enable diagnostics; invalid shared/output config is rejected", () => {
    const { d, deployment, def } = fixture();
    delete def.podResilience;
    delete def.outputOverrides;
    const saved = JSON.stringify(d);
    const imported = validateSimulationModel(JSON.parse(saved));
    expect((imported.nodes.find((n: StudioModelNode) => n.type === "kubernetes-deployment")!.config.deployment as DeploymentDefinition).podResilience).toBeUndefined();
    const s = stepSimulation(d);
    expect(s.controllers![deployment.id].instances.every((p: any) => p.health === undefined)).toBe(true);
    def.podResilience = { ...podResilienceDefaults, crashAfterTicks: 1.5 };
    expect(() => validateDeployment(def)).toThrow(/crashAfterTicks/);
    delete def.podResilience;
    def.outputOverrides = { "http-out": 4 };
    expect(() => validateDeployment(def)).toThrow(/output override/);
  });

  it("Controller resilience can stop dispatch independently of child diagnostic readiness", () => {
    const { d, deployment } = fixture();
    model(deployment).crashAfterTicks = 2;
    let s = stepSimulation(d);
    expect(s.nodes[deployment.id].autoFailed).toBe(false);
    s = stepSimulation(d, s);
    expect(s.nodes[deployment.id].autoFailed).toBe(true);
    expect(s.summary!.completed).toBe(0);
    expect(s.controllers![deployment.id].instances.every((p: any) => p.processed === 0)).toBe(true);
  });

  it("Slow affects one instance, unequal capacities conserve dispatched work, and Restore all includes physical Pod faults", () => {
    const { d, deployment, client } = fixture();
    model(client).rate = 500;
    let s = stepSimulation(d);
    const id = s.controllers![deployment.id].instances[0].id;
    s.controllers![deployment.id] = controllerCommand(deployment, s.controllers![deployment.id], "slow", id);
    expect(controllerFaults(s).length).toBe(1);
    s = stepSimulation(d, s);
    expect(s.controllers![deployment.id].instances.map((p: any) => p.processed)).toEqual([60, 250]);
    expect(s.controllers![deployment.id].processed).toBe(310);
    expect(s.nodes[deployment.id].processed).toBe(310);
    expect(s.summary!.completed).toBe(310);
    modelCommand(s, d, "restore-all");
    expect(controllerFaults(s).length).toBe(0);
    s = stepSimulation(d, s);
    expect(s.summary!.completed).toBe(500);
    expect(s.controllers![deployment.id].ready).toBe(2);
    s.controllers![deployment.id] = controllerCommand(deployment, s.controllers![deployment.id], "crash", id);
    expect(controllerFaults(s)[0].kind).toBe("crash");
    modelCommand(s, d, "restore-all");
    s = stepSimulation(d, s);
    expect(s.controllers![deployment.id].ready).toBe(2);
    expect(controllerFaults(s).length).toBe(0);
  });

  it("Zero readiness restores immediately, while explicit two-tick readiness waits exactly two ticks", () => {
    const { d, deployment, def } = fixture();
    let s = stepSimulation(d), c = s.controllers![deployment.id];
    const id = c.instances[0].id;
    def.readinessTicks = 0;
    c = controllerCommand(deployment, c, "crash", id);
    c = controllerCommand(deployment, c, "restore", id);
    expect(c.instances[0].readiness).toBe("ready");
    def.readinessTicks = 2;
    c = controllerCommand(deployment, c, "crash", id);
    c = controllerCommand(deployment, c, "restore", id);
    s.controllers![deployment.id] = c;
    s = stepSimulation(d, s);
    expect(s.controllers![deployment.id].instances[0].readyIn).toBe(1);
    s = stepSimulation(d, s);
    expect(s.controllers![deployment.id].instances[0].readiness).toBe("ready");
  });
});
