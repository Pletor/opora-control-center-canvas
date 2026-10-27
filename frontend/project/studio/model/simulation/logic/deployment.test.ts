// Převedeno z prototypu `test/deployment.test.mjs`; vynecháno: nic (export/import projektu nahrazen JSON round-tripem modelu).
import { describe, expect, it } from "vitest";
import { connect } from "../../logic/model-rules";
import { emptyStudioModel, type PortRef, type StudioModel } from "../../logic/model-types";
import { controllerCommand, deploymentDefinition, reconcileDeployment, validateDeployment } from "./deployment";
import { createSimulationNode, simulationDomain } from "./model-adapter";
import { createSimulation, modelCommand, stepSimulation } from "./simulation";
import type { DeploymentDefinition, SimNode } from "./simulation-types";
import { validateSimulationModel } from "./simulation-validate";

/** Uzel tak, jak ho čte engine: jen id a definice šablony Podů. */
const node = (): SimNode => ({ id: "deployment", deployment: deploymentDefinition("shared-template") }) as unknown as SimNode;
const def = (n: SimNode) => n.deployment as DeploymentDefinition;

/** Přidá vazbu do modelu na místě (S4 `connect` vrací nový model) a vrátí ji. */
function link(d: StudioModel, from: PortRef, to: PortRef) {
  const r = connect(d, from, to);
  d.edges = r.model.edges;
  return r.edge;
}

describe("deployment", () => {
  it("Observed deployment: two ready Pods; 250→125+125 and threshold4500/4501", () => {
    const n = node(), initial = reconcileDeployment(n);
    expect(initial.actual).toBe(2);
    expect(initial.ready).toBe(2);
    const a = reconcileDeployment(n, initial, { offered: 250, tick: true });
    expect(a.instances.map((p) => p.offered)).toEqual([125, 125]);
    const b = reconcileDeployment(n, a, { offered: 4500 });
    expect(b.actual).toBe(2);
    const c = reconcileDeployment(n, b, { offered: 4501 });
    expect(c.actual).toBe(3);
    expect(c.ready).toBe(3);
    const d = reconcileDeployment(n, c, { offered: 6000 });
    expect(d.instances.map((p) => p.offered)).toEqual([2000, 2000, 2000]);
    expect(d.processed).toBe(6000);
  });

  it("Minimum edits grow ready immediately; excess replicas shrink one per three steps", () => {
    const n = node();
    let s = reconcileDeployment(n);
    def(n).minReplicas = 3;
    s = reconcileDeployment(n, s);
    expect(s.ready).toBe(3);
    def(n).minReplicas = 2;
    s = reconcileDeployment(n, s);
    expect(s.recommended).toBe(2);
    expect(s.actual).toBe(3);
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.actual).toBe(3);
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.actual).toBe(3);
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.actual).toBe(2);
  });

  it("Failed instance replaced at second tick, initializing until next tick; local overrides do not transfer", () => {
    const n = node();
    let s = reconcileDeployment(n);
    const original = s.instances[0].id;
    s.instances[0].overrides["sql-out"] = 123;
    s = controllerCommand(n, s, "crash", original);
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.ready).toBe(1);
    expect(s.instances[0].id).toBe(original);
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.ready).toBe(1);
    expect(s.instances[0].id).not.toBe(original);
    expect(s.instances[0].state).toBe("initializing");
    expect(s.instances[0].readyIn).toBe(1);
    expect(s.instances[0].overrides).toEqual({});
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.ready).toBe(2);
    expect(s.instances[0].templateId).toBe("shared-template");
  });

  it("Pressure10800 initializes two Pods; restore downscales at ticks3 and6 without random values", () => {
    const n = node();
    let s = controllerCommand(n, reconcileDeployment(n), "pressure");
    expect(s.offered).toBe(10800);
    expect(s.actual).toBe(4);
    expect(s.ready).toBe(2);
    s = reconcileDeployment(n, s, { tick: true });
    expect(s.ready).toBe(4);
    s = controllerCommand(n, s, "external");
    expect(s.offered).toBe(0);
    expect(s.recommended).toBe(2);
    expect(s.recoveryRemaining).toBe(2);
    const states: number[] = [];
    for (let i = 0; i < 6; i++) { s = reconcileDeployment(n, s, { tick: true }); states.push(s.actual); }
    expect(states).toEqual([4, 4, 3, 3, 3, 2]);
    expect(s.recoveryRemaining).toBe(0);
  });

  it("Shared template update affects siblings; snapshots and invalid definitions preserve isolation", () => {
    const n = node(), a = reconcileDeployment(n);
    def(n).podCapacity = 1000;
    const b = reconcileDeployment(n, a, { offered: 250 });
    expect(b.instances.map((p) => p.capacity)).toEqual([1000, 1000]);
    expect(a.instances.map((p) => p.capacity)).toEqual([3000, 3000]);
    def(n).maxReplicas = 1;
    expect(() => validateDeployment(def(n))).toThrow(/Minimum/);
    def(n).maxReplicas = 4;
    def(n).readinessTicks = .5;
    expect(() => validateDeployment(def(n))).toThrow(/readinessTicks/);
  });

  it("Actual graph routes250 through LB and Pods, returns DB failures, and stores definition without runtime instances", () => {
    const d = emptyStudioModel("deployment-graph");
    const [client, lb, deployment, db] = ["client", "load-balancer", "kubernetes-deployment", "postgresql"].map((type) => createSimulationNode(type));
    d.nodes.push(client, lb, deployment, db);
    lb.config.model = { capacity: 100000, concurrency: 10000 };
    db.config.model = { capacity: 100000, concurrency: 10000 };
    link(d, { nodeId: client.id, portId: "http-out" }, { nodeId: lb.id, portId: "http-in" });
    link(d, { nodeId: lb.id, portId: "http-out" }, { nodeId: deployment.id, portId: "http-in" });
    link(d, { nodeId: deployment.id, portId: "sql-out" }, { nodeId: db.id, portId: "sql-in" });
    const saved = JSON.stringify(d);
    const sim = simulationDomain(d).nodes.find((n) => n.id === deployment.id)!;
    let s = stepSimulation(d, createSimulation());
    expect(s.summary!.completed).toBe(250);
    expect(s.controllers![deployment.id].instances.map((p: any) => p.completed)).toEqual([125, 125]);
    const id = s.controllers![deployment.id].instances[0].id;
    s.controllers![deployment.id] = controllerCommand(sim, s.controllers![deployment.id], "crash", id);
    s = stepSimulation(d, s);
    expect(s.summary!.completed).toBe(250);
    expect(s.controllers![deployment.id].ready).toBe(1);
    modelCommand(s, d, "crash", [db.id]);
    s = stepSimulation(d, s);
    expect(s.summary!.completed).toBe(0);
    expect(s.controllers![deployment.id].instances.every((p: any) => p.completed === 0)).toBe(true);
    expect(JSON.stringify(d)).toBe(saved);
    expect(validateSimulationModel(JSON.parse(saved))).toEqual(d);
    expect(saved.includes(":pod:")).toBe(false);
    const old = JSON.parse(saved);
    delete old.nodes.find((n: any) => n.id === deployment.id).config.deployment;
    expect(() => validateSimulationModel(old)).not.toThrow();
  });

  it("Template identities are unique; an instance override changes actual aggregate SQL and vanishes on replacement", () => {
    const d = emptyStudioModel("deployment-identity");
    const deployment = createSimulationNode("kubernetes-deployment"), db = createSimulationNode("postgresql");
    const client = createSimulationNode("client"), lb = createSimulationNode("load-balancer");
    d.nodes.push(deployment, db, client, lb);
    link(d, { nodeId: client.id, portId: "http-out" }, { nodeId: lb.id, portId: "http-in" });
    link(d, { nodeId: lb.id, portId: "http-out" }, { nodeId: deployment.id, portId: "http-in" });
    const edge = link(d, { nodeId: deployment.id, portId: "sql-out" }, { nodeId: db.id, portId: "sql-in" });
    let s = stepSimulation(d);
    s.controllers![deployment.id].instances[0].overrides["sql-out"] = 123;
    s = stepSimulation(d, s);
    expect(s.edges[edge.id].offered).toBe(248);
    const other = createSimulationNode("kubernetes-deployment");
    (other.config.deployment as DeploymentDefinition).templateId = (deployment.config.deployment as DeploymentDefinition).templateId;
    d.nodes.push(other);
    expect(() => validateSimulationModel(d)).toThrow(/Duplicitní identita/);
  });
});
