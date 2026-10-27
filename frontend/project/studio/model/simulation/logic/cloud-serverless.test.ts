// Převedeno z prototypu `test/cloud-serverless.test.mjs`; vynecháno: nic (export/import projektu nahrazen JSON round-tripem modelu).
import { describe, expect, it } from "vitest";
import { TYPED_POLICY } from "../../logic/connection-policy";
import { connect, connectionError } from "../../logic/model-rules";
import { emptyStudioModel, type PortRef, type StudioModel, type StudioModelNode } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";

const types = ["aws-lambda", "gcp-cloud-run", "aliyun-fc"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);
const model = (n: StudioModelNode) => n.config.model as Record<string, any>;

function fixture(type: string) {
  const d = materializeScenario("cloud-serverless-" + type);
  const pick = (t: string) => d.nodes.find((n) => n.type === t)!;
  return { d, f: pick(type), db: pick("postgresql"), monitor: pick("monitoring") };
}

/** Přidá vazbu do modelu na místě (S4 `connect` vrací nový model). */
function link(d: StudioModel, from: PortRef, to: PortRef) {
  const r = connect(d, from, to);
  d.edges = r.model.edges;
  return r.edge;
}

describe("cloud-serverless", () => {
  it("All provider HTTP pipelines calculate SQL completion and actual offered telemetry from the same handler work", () => {
    for (const type of types) {
      const { d, f, db, monitor } = fixture(type);
      const s = stepSimulation(d), r = s.nodes[f.id];
      near(r.offered, 250); near(r.processed, 250); near(r.completed, 250);
      near(s.nodes[db.id].offered, 250); near(s.nodes[monitor.id].offered, 5); near(s.summary!.completed, 250);
      expect(r.technology.modelVersion).toBe("serverless-model/1");
      expect(r.technology.activeInstances).toBeGreaterThanOrEqual(1);
      expect(stepSimulation(d)).toEqual(s);
    }
  });

  it("Controlled source capacity cases have independently documented 10/20/10 ceilings and corresponding backpressure", () => {
    for (const type of types) {
      const { d, f } = fixture(type);
      f.config.model = { coldStartShare: 0, serviceLatencyMs: 100, reservedConcurrency: 1, instanceConcurrency: 1, crashAfterTicks: 0 };
      const r = stepSimulation(d), expected = type === "gcp-cloud-run" ? 20 : 10;
      near(r.nodes[f.id].capacity, expected); near(r.nodes[f.id].processed, expected);
      near(r.nodes[f.id].rejected, 250 - expected); near(r.summary!.completed, expected);
      expect(r.events.some((e) => e.kind === "serverless-throttled")).toBe(true);
    }
    const { d, f } = fixture("gcp-cloud-run");
    f.config.model = { coldStartShare: 0, serviceLatencyMs: 100, reservedConcurrency: 1, instanceConcurrency: 2 };
    near(stepSimulation(d).nodes[f.id].processed, 40);
    model(f).memoryMb = 1024;
    near(stepSimulation(d).nodes[f.id].processed, 20);
    model(f).instanceConcurrency = 1; model(f).coldStartShare = 1; model(f).coldStartLatencyMs = 100;
    near(stepSimulation(d).nodes[f.id].processed, 5);
  });

  it("SQL failure propagates along actual synchronous dependencies while telemetry remains offered local work", () => {
    const { d, f, db, monitor } = fixture("aws-lambda");
    let s = stepSimulation(d);
    modelCommand(s, d, "crash", [db.id]);
    s = stepSimulation(d, s);
    near(s.nodes[f.id].processed, 250); near(s.nodes[f.id].completed, 0); near(s.nodes[monitor.id].offered, 5); near(s.summary!.completed, 0);
    modelCommand(s, d, "restore", [db.id]);
    for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
    near(s.summary!.completed, 250);
    modelCommand(s, d, "crash", [f.id]);
    s = stepSimulation(d, s);
    near(s.nodes[f.id].technology.unavailable, 250); near(s.nodes[f.id].technology.throttled, 0);
    near(s.nodes[monitor.id].offered, 0); near(s.summary!.completed, 0);
    modelCommand(s, d, "restore", [f.id]);
    for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
    near(s.summary!.completed, 250);
  });

  it("Output overrides are explicit saved offers; downstream partial admission and failure cannot manufacture success", () => {
    const { d, f, db, monitor } = fixture("aws-lambda");
    f.config.outputOverrides = { "sql-out": 1000, "telemetry-out": 9 };
    db.config.model = { capacity: 500 };
    let s = stepSimulation(d);
    near(s.nodes[db.id].offered, 1000); near(s.nodes[monitor.id].offered, 9); near(s.nodes[f.id].completed, 125);
    modelCommand(s, d, "crash", [f.id]);
    s = stepSimulation(d, s);
    near(s.nodes[db.id].offered, 0); near(s.nodes[monitor.id].offered, 0); near(s.nodes[f.id].completed, 0);
  });

  it("Actual connected cache hit budget reduces SQL and failed or disabled cache falls back without invented hits", () => {
    for (const type of types) {
      const { d, f, db } = fixture(type), cache = createSimulationNode("redis", { x: 640, y: 350 });
      d.nodes.push(cache);
      link(d, { nodeId: f.id, portId: "cache-out" }, { nodeId: cache.id, portId: "cache-in" });
      let s = stepSimulation(d);
      near(s.nodes[f.id].technology.cacheHits, 200); near(s.nodes[db.id].offered, 50); near(s.summary!.completed, 250);
      modelCommand(s, d, "crash", [db.id]);
      s = stepSimulation(d, s);
      near(s.nodes[f.id].completed, 200);
      modelCommand(s, d, "restore", [db.id]);
      for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
      modelCommand(s, d, "crash", [cache.id]);
      s = stepSimulation(d, s);
      near(s.nodes[f.id].technology.cacheHits, 0); near(s.nodes[db.id].offered, 250); near(s.summary!.completed, 250);
      modelCommand(s, d, "restore", [cache.id]);
      for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
      near(s.nodes[db.id].offered, 50);
      f.config.outputOverrides = { "cache-out": 0 };
      s = stepSimulation(d);
      near(s.nodes[db.id].offered, 250); near(s.nodes[cache.id].offered, 0);
    }
  });

  it("Observed asynchronous role exclusions apply to new serverless types in v2, explicit typed extension remains possible", () => {
    for (const type of types) for (const [source, out, input] of [["event-producer", "event-out", "event-in"], ["queue", "job-out", "job-in"]]) {
      const d = emptyStudioModel("d"), a = createSimulationNode(source), f = createSimulationNode(type);
      d.nodes.push(a, f);
      const from = { nodeId: a.id, portId: out }, to = { nodeId: f.id, portId: input };
      expect(connectionError(d, from, to)).toBeTruthy();
      expect(connectionError(d, from, to, undefined, TYPED_POLICY)).toBeNull();
      connect(d, from, to, TYPED_POLICY);
    }
    const d = emptyStudioModel("d"), producer = createSimulationNode("event-producer"), f = createSimulationNode("aws-lambda");
    d.nodes.push(producer, f);
    d.edges = connect(d, { nodeId: producer.id, portId: "event-out" }, { nodeId: f.id, portId: "event-in" }, TYPED_POLICY).model.edges;
    near(stepSimulation(d).nodes[f.id].processed, 250);
  });

  it("Logical replica scaling is bounded and low-pressure removal needs committed stabilization steps; previews are pure", () => {
    const { d, f } = fixture("aws-lambda");
    f.config.model = { reservedConcurrency: 1, serviceLatencyMs: 100, coldStartShare: 0, minInstances: 1, maxInstances: 3, autoscaleTargetPct: 70, autoscaleScaleDownTicks: 2, crashAfterTicks: 0 };
    let s = stepSimulation(d);
    expect(s.nodes[f.id].replicas).toBe(1);
    s = stepSimulation(d, s);
    expect(s.nodes[f.id].replicas).toBe(2);
    const before = structuredClone(s), p = previewSimulation(d, s);
    expect(s).toEqual(before);
    expect(p.nodes[f.id].replicas).toBe(2);
    s = stepSimulation(d, s);
    expect(s.nodes[f.id].replicas).toBe(3);
    model(d.nodes.find((n) => n.type === "client")!).rate = 0;
    s = stepSimulation(d, s); s = stepSimulation(d, s);
    expect(s.nodes[f.id].replicas).toBe(3);
    s = stepSimulation(d, s);
    expect(s.nodes[f.id].replicas).toBe(2);
  });

  it("Definitions roundtrip without runtime invocations and reject invalid source bounds, cross-limits and output offers", () => {
    for (const type of types) {
      const { d, f } = fixture(type);
      f.config.outputOverrides = { "sql-out": 27.5 };
      const raw = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(raw))).toEqual(d);
      expect(raw.includes("activeInstances")).toBe(false);
      expect(raw.includes("coldInvocations")).toBe(false);
      for (const patch of [{ minInstances: 4, maxInstances: 2 }, { memoryMb: 1 }, { instanceConcurrency: 1.5 }, { coldStartShare: 2 }]) {
        f.config.model = patch;
        expect(() => validateSimulationModel(d)).toThrow();
      }
      f.config.model = {};
      for (const value of [-1, NaN, Infinity]) {
        f.config.outputOverrides = { "sql-out": value };
        expect(() => validateSimulationModel(d)).toThrow();
      }
      f.config.outputOverrides = { "invalid-port": 2 };
      expect(() => validateSimulationModel(d)).toThrow();
    }
  });
});
