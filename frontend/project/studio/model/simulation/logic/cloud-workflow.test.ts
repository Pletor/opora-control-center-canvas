// Převedeno z prototypu `test/cloud-workflow.test.mjs`; vynecháno: nic (export/import projektu nahrazen JSON round-tripem modelu).
import { describe, expect, it } from "vitest";
import { connect, removeNode } from "../../logic/model-rules";
import type { PortRef, StudioModel, StudioModelNode } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { createSimulation, modelCommand, previewSimulation, rebaseSimulation, stepSimulation } from "./simulation";
import { validateModelConfig } from "./simulation-config";
import { validateSimulationModel } from "./simulation-validate";

const types = ["aws-step-functions", "gcp-workflows", "aliyun-fnf"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-6);
const model = (n: StudioModelNode) => n.config.model as Record<string, any>;

function fixture(type: string) {
  const d = materializeScenario("cloud-workflow-" + type);
  const pick = (t: string) => d.nodes.find((n) => n.type === t)!;
  return { d, w: pick(type), worker: pick("worker"), producer: pick("event-producer"), db: pick("postgresql") };
}

/** Přidá vazbu do modelu na místě (S4 `connect` vrací nový model). */
function link(d: StudioModel, from: PortRef, to: PortRef) {
  d.edges = connect(d, from, to).model.edges;
}

/** Zachování: přijaté − uzavřené = aktivní, uzavřené − emitované = čekající události. */
function conserve(r: Record<string, any>) {
  near(r.totals.accepted - r.totals.terminal, r.active);
  near(r.totals.terminal - r.totals.emitted, r.pendingEvents);
}

describe("cloud-workflow", () => {
  it("Each provider dispatch records actual Worker and SQL completion, then settles only in the next step", () => {
    for (const type of types) {
      const { d, w, worker } = fixture(type);
      let s = stepSimulation(d);
      const r = s.nodes[w.id];
      near(r.processed, 247.5); near(r.completed, 0); near(r.technology.active, 247.5); near(r.technology.canceled, 2.5);
      expect(r.technology.batches[0].receipt.routes[0].targetId).toBe(worker.id);
      near(r.technology.batches[0].outcome, 1);
      expect(r.state).toBe("healthy");
      const previous = s, before = structuredClone(s);
      s = stepSimulation(d, s);
      expect(previous).toEqual(before);
      near(s.nodes[w.id].completed, 247.5);
      conserve(s.nodes[w.id].technology);
      expect(s.events.some((e) => e.kind === "workflow-succeeded")).toBe(true);
    }
  });

  it("A downstream model failure creates an actual failed receipt; compensate and retries are not invented successes", () => {
    for (const type of types) {
      const { d, w, worker } = fixture(type);
      let s = stepSimulation(d);
      modelCommand(s, d, "crash", [worker.id]);
      s = stepSimulation(d, s);
      near(s.nodes[w.id].completed, 247.5); near(s.nodes[w.id].technology.batches[0].outcome, 0);
      model(w).failurePolicy = "compensate";
      s = stepSimulation(d, s);
      near(s.nodes[w.id].technology.compensated, 247.5); near(s.nodes[w.id].completed, 0);
      expect(s.events.some((e) => e.kind === "workflow-compensated")).toBe(true);
      conserve(s.nodes[w.id].technology);
    }
  });

  it("Replacing the worker cannot rewrite an earlier failure; only a later retried dispatch to the new worker succeeds", () => {
    const { d, w, worker, producer, db } = fixture(types[0]);
    const initial = createSimulation();
    modelCommand(initial, d, "crash", [worker.id]);
    let s = stepSimulation(d, initial);
    near(s.nodes[w.id].technology.batches[0].outcome, 0);
    const old = structuredClone(d), replacement = createSimulationNode("worker");
    model(producer).rate = 0;
    const without = removeNode(d, worker.id);
    d.nodes = [...without.nodes, replacement]; d.edges = without.edges;
    link(d, { nodeId: w.id, portId: "job-out" }, { nodeId: replacement.id, portId: "job-in" });
    link(d, { nodeId: replacement.id, portId: "sql-out" }, { nodeId: db.id, portId: "sql-in" });
    s = rebaseSimulation(d, s, old);
    const before = structuredClone(s), p = previewSimulation(d, s);
    expect(s).toEqual(before);
    near(p.nodes[w.id].technology.active, 247.5);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].technology.retried, 247.5); near(s.nodes[w.id].completed, 0);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].processed, 0);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].processed, 247.5);
    expect(s.nodes[w.id].technology.batches[0].receipt.routes[0].targetId).toBe(replacement.id);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].completed, 247.5); near(s.nodes[w.id].technology.active, 0);
    conserve(s.nodes[w.id].technology);
  });

  it("Delayed cycle dispatch keeps origin tick and cannot consume unrelated current-frame completion", () => {
    const { d, w, worker } = fixture(types[0]);
    model(worker).eventShare = 0;
    d.nodes = [worker, ...d.nodes.filter((n) => n.id !== worker.id)];
    link(d, { nodeId: worker.id, portId: "event-out" }, { nodeId: w.id, portId: "event-in" });
    const job = d.edges.find((e) => e.from.nodeId === w.id)!;
    let s = stepSimulation(d);
    expect(s.edges[job.id].delayed).toBe(true);
    near(s.nodes[worker.id].processed, 0);
    expect(s.nodes[w.id].technology.batches[0].outcome).toBe(null);
    expect(s.edges[job.id].nextDispatchTick).toBe(1);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].completed, 0);
    expect(s.edges[job.id].dispatchTick).toBe(1);
    const batch = s.nodes[w.id].technology.batches.find((b: any) => b.dispatchTick === 1);
    near(batch.outcome, 1);
    expect(batch.receipt.routes[0].observed.tick).toBe(2);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].completed, 247.5);
    conserve(s.nodes[w.id].technology);
  });

  it("Parameter edits preserve committed cohorts in preview; shrinking capacity only restricts new work on Step", () => {
    const { d, w } = fixture(types[0]);
    let s = stepSimulation(d);
    const before = structuredClone(s);
    w.config.model = { maxActive: 1, dispatchRps: 0, crashAfterTicks: 0 };
    const p = previewSimulation(d, s);
    expect(s).toEqual(before);
    expect(p.nodes[w.id].technology.batches).toEqual(s.nodes[w.id].technology.batches);
    near(p.nodes[w.id].technology.active, 247.5);
    expect(p.nodes[w.id].technology.configurationPending).toBe(true);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].completed, 247.5); near(s.nodes[w.id].technology.active, 1);
    near(s.nodes[w.id].processed, 0); near(s.nodes[w.id].technology.overflow, 246.5);
    conserve(s.nodes[w.id].technology);
  });

  it("Physical workflow outage has no dispatch or emitted outputs, server timeouts enter outbox and recovery releases them", () => {
    const { d, w } = fixture(types[0]);
    w.config.model = { timeoutTicks: 3 };
    let s = stepSimulation(d);
    modelCommand(s, d, "crash", [w.id]);
    for (let i = 0; i < 3; i++) s = stepSimulation(d, s);
    near(s.nodes[w.id].technology.totals.timedOut, 247.5); near(s.nodes[w.id].technology.pendingEvents, 247.5);
    near(s.nodes[w.id].processed, 0); near(s.nodes[w.id].technology.eventOut, 0);
    modelCommand(s, d, "restore-all");
    for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
    expect(s.nodes[w.id].technology.totals.emitted).toBeGreaterThanOrEqual(250);
    conserve(s.nodes[w.id].technology);
  });

  it("New workflow enum definitions roundtrip without runtime receipts, and invalid configuration fails closed", () => {
    const { d, w } = fixture(types[0]);
    w.config.model = { failurePolicy: "compensate", timerAuthority: "client", retryLimit: 2 };
    const json = JSON.stringify(d);
    const restored = validateSimulationModel(JSON.parse(json));
    expect(restored).toEqual(d);
    expect(json.includes('"receipt":')).toBe(false);
    expect(stepSimulation(d)).toEqual(stepSimulation(restored));
    for (const value of [{ failurePolicy: "ignore" }, { timerAuthority: "whatever" }, { retryLimit: 1.5 }, { maxActive: -1 }, { timeoutTicks: 0 }])
      expect(() => validateModelConfig(value)).toThrow();
  });

  it("Removing an unreceived delayed dispatch fails that receipt even while another healthy worker completes unrelated jobs", () => {
    const { d, w, worker, producer, db } = fixture(types[0]);
    model(worker).eventShare = 0;
    d.nodes = [worker, ...d.nodes.filter((n) => n.id !== worker.id)];
    link(d, { nodeId: worker.id, portId: "event-out" }, { nodeId: w.id, portId: "event-in" });
    const job = d.edges.find((e) => e.from.nodeId === w.id)!;
    let s = stepSimulation(d);
    expect(s.nodes[w.id].technology.batches[0].outcome).toBe(null);
    const old = structuredClone(d);
    const replacement = createSimulationNode("worker"), other = createSimulationNode("event-producer"), queue = createSimulationNode("queue");
    other.config.model = { rate: 50 };
    model(producer).rate = 0;
    d.edges = d.edges.filter((e) => e.id !== job.id);
    d.nodes.push(replacement, other, queue);
    link(d, { nodeId: w.id, portId: "job-out" }, { nodeId: replacement.id, portId: "job-in" });
    link(d, { nodeId: other.id, portId: "event-out" }, { nodeId: queue.id, portId: "event-in" });
    link(d, { nodeId: queue.id, portId: "job-out" }, { nodeId: replacement.id, portId: "job-in" });
    link(d, { nodeId: replacement.id, portId: "sql-out" }, { nodeId: db.id, portId: "sql-in" });
    s = rebaseSimulation(d, s, old);
    s = stepSimulation(d, s);
    expect(s.nodes[replacement.id].completed).toBeGreaterThan(0);
    const original = s.nodes[w.id].technology.batches.find((b: any) => b.dispatchTick === 1);
    expect(original.outcome).toBe(0);
    expect(original.receipt.routes[0].reason).toBe("route-changed");
    near(s.nodes[w.id].completed, 0);
    s = stepSimulation(d, s);
    near(s.nodes[w.id].completed, 0); near(s.nodes[w.id].technology.retried, 247.5);
    conserve(s.nodes[w.id].technology);
  });
});
