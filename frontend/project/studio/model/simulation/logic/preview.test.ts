// Převedeno z prototypu `test/preview.test.mjs`; vynecháno: nic.
import { describe, expect, it } from "vitest";
import type { StudioModel } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { createSimulation, modelCommand, previewSimulation, stepSimulation } from "./simulation";

const find = (d: StudioModel, type: string) => d.nodes.find((n) => n.type === type)!;
const model = (n: { config: Record<string, unknown> }) => n.config.model as Record<string, any>;

describe("preview", () => {
  it("Preview immediately recalculates the whole graph without advancing time or history", () => {
    const d = materializeScenario("web-chain"), client = find(d, "client"), s = stepSimulation(d), before = structuredClone(s);
    model(client).concurrency = 1;
    const preview = previewSimulation(d, s);
    expect(preview.preview).toBe(true);
    expect(preview.tick).toBe(s.tick);
    expect(preview.nodes[client.id].latencyMs).toBe(3000);
    expect(preview.summary!.completed).toBe(80);
    expect(preview.events).toEqual(s.events);
    expect(preview.samples).toEqual(s.samples);
    expect(s).toEqual(before);
    const next = stepSimulation(d, s);
    expect(next.tick).toBe(s.tick + 1);
    expect(next.summary!.completed).toBe(80);
    expect(next.preview).toBe(false);
  });

  it("Repeated previews do not consume queued work or duplicate the next tick", () => {
    const d = materializeScenario("queue-backpressure"), queue = find(d, "queue"), worker = find(d, "worker"), s = stepSimulation(d);
    expect(s.nodes[queue.id].backlog).toBe(150);
    model(worker).capacity = 200;
    const before = structuredClone(s);
    for (let i = 0; i < 20; i++) {
      const p = previewSimulation(d, s);
      expect(p.nodes[queue.id].backlog).toBe(150);
      expect(p.nodes[worker.id].processed).toBe(200);
      expect(p.samples).toEqual(s.samples);
    }
    expect(s).toEqual(before);
    const next = stepSimulation(d, s);
    expect(next.nodes[queue.id].backlog).toBe(200);
    expect(next.tick).toBe(2);
  });

  it("Preview does not advance manual recovery, overload counters, or scheduled incidents", () => {
    const d = materializeScenario("web-chain"), db = find(d, "postgresql"), service = find(d, "service"), monitor = createSimulationNode("monitoring");
    d.nodes.push(monitor);
    service.config.model = { capacity: 50, crashAfterTicks: 2 };
    const s = stepSimulation(d);
    expect(s.nodes[service.id].overloadTicks).toBe(1);
    modelCommand(s, d, "restore", [db.id]);
    d.modelDefinition.incidents = [{ tick: 2, kind: "crash", nodeIds: [monitor.id] }];
    for (let i = 0; i < 10; i++) {
      const p = previewSimulation(d, s);
      expect(p.nodes[service.id].overloadTicks).toBe(1);
      expect(p.nodes[service.id].autoFailed).toBe(false);
      expect(p.incidents[db.id].remaining).toBe(2);
      expect(Object.keys(p.incidents).length).toBe(1);
    }
    const next = stepSimulation(d, s);
    expect(next.nodes[service.id].autoFailed).toBe(true);
    expect(next.incidents[db.id].remaining).toBe(1);
    expect(Object.keys(next.incidents).length).toBe(2);
  });

  it("Deployment preview reconciles declarative load changes with ready Pods and no controller timer ticks", () => {
    const d = materializeScenario("deployment-scaling"), client = find(d, "client"), deployment = find(d, "kubernetes-deployment");
    const s = stepSimulation(d), before = structuredClone(s);
    model(client).rate = 6000;
    model(client).concurrency = 1000;
    const p = previewSimulation(d, s), c = p.controllers![deployment.id];
    expect(c.actual).toBe(3);
    expect(c.ready).toBe(3);
    expect(c.instances.map((i: any) => i.offered)).toEqual([2000, 2000, 2000]);
    expect(p.summary!.completed).toBe(6000);
    expect(p.tick).toBe(s.tick);
    expect(s).toEqual(before);
    const adopted = structuredClone(s);
    adopted.controllers = structuredClone(p.controllers);
    const next = stepSimulation(d, adopted);
    expect(next.controllers![deployment.id].ready).toBe(3);
    expect(next.summary!.completed).toBe(6000);
  });

  it("Preview cannot finish a client recovery or progress a breaker timer", () => {
    const d = materializeScenario("web-chain"), client = find(d, "client");
    model(client).concurrency = 1;
    const s = stepSimulation(d);
    model(client).concurrency = 400;
    const p = previewSimulation(d, s);
    expect(p.nodes[client.id].state).toBe("recovering");
    expect(p.nodes[client.id].flowRecoveryProgress).toBe(0);
    expect(stepSimulation(d, s).nodes[client.id].flowRecoveryProgress).toBe(1);
    const b = materializeScenario("breaker-recovery");
    let state = createSimulation();
    for (let i = 0; i < 7; i++) state = stepSimulation(b, state);
    const breaker = find(b, "circuit-breaker"), before = structuredClone(state);
    for (let i = 0; i < 10; i++) {
      const frame = previewSimulation(b, state);
      expect(frame.nodes[breaker.id].circuit).toBe(state.nodes[breaker.id].circuit);
      expect(frame.nodes[breaker.id].openUntil).toBe(state.nodes[breaker.id].openUntil);
    }
    expect(state).toEqual(before);
  });
});
