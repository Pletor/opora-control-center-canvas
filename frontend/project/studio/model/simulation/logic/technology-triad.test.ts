// Převedeno z prototypu `test/technology-triad.test.mjs`; vynecháno: nic. Zdrojová pozorování výchozích hodnot jsou konstanty
// z `analysis/evidence/extended-catalog-observations.json` (items[].defaults pro id service-mesh, vector-db, cdc-connector).
import { describe, expect, it } from "vitest";
import { cdcDefaults, cdcCapture, meshDefaults, vectorDefaults } from "./technology";
import { materializeScenario } from "./scenarios";
import { config, validateModelConfig } from "./simulation-config";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";

const resilience = { stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2 };
const scale = { minInstances: 1, maxInstances: 1, autoscaleTargetPct: 70, autoscaleScaleDownTicks: 3 };
const source: Record<string, Record<string, number>> = {
  "service-mesh": { proxyCapacityRps: 35000, mtlsOverheadMs: 2, retryBudgetPct: 20, outlierThresholdPct: 50, serviceLatencyMs: 2, ...resilience, ...scale },
  "vector-db": { queryCapacityRps: 12000, upsertCapacityRps: 6000, efSearch: 64, dimensions: 1536, indexMemoryLimitGb: 32, workingSetGb: 20, serviceLatencyMs: 8, ...resilience, ...scale },
  "cdc-connector": { captureCapacityRps: 15000, snapshotBatchSize: 500, walLagLimit: 50000, transformMs: 4, schemaErrorRate: .01, serviceLatencyMs: 6, ...resilience, ...scale },
};
type D = ReturnType<typeof materializeScenario>;
const find = (d: D, type: string) => d.nodes.find((n) => n.type === type)!;
const model = (node: { config: Record<string, unknown> }) => node.config.model as Record<string, any>;
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-6);

describe("technology-triad", () => {
  it("Mesh Vector CDC defaults agree with independent source observations and integer fields reject invalid values", () => {
    for (const [type, defaults] of [["service-mesh", meshDefaults], ["vector-db", vectorDefaults], ["cdc-connector", cdcDefaults]] as const)
      for (const [key, value] of Object.entries(defaults)) expect(value, `${type}.${key}`).toBe(source[type][key]);
    for (const key of ["efSearch", "dimensions", "snapshotBatchSize"]) expect(() => validateModelConfig({ [key]: 1.5 })).toThrow(/celé/);
  });
  it("Mesh shares attempt capacity, bounds retries and quarantines exactly one tick before a successful probe", () => {
    const d = materializeScenario("mesh-resilience"), mesh = find(d, "service-mesh"), service = find(d, "service");
    d.modelDefinition.incidents = []; mesh.config.model = { outlierThresholdPct: 0, retryBudgetPct: 20 }; model(service).capacity = 100;
    let s = stepSimulation(d);
    near(s.nodes[mesh.id].completed, 100);
    const original = structuredClone(s);
    const next = stepSimulation(d, s), r = next.nodes[mesh.id];
    expect(s).toEqual(original);
    near(r.technology.attempts, 300); near(r.technology.retries, 50); near(r.capacity, 35000 / 1.2); near(r.completed, 250 * (1 - Math.pow(2 / 3, 1.2)));
    near(next.edges[d.edges.find((e) => e.from.nodeId === mesh.id && e.type === "http-request")!.id].offered, 300);
    const before = structuredClone(next), preview = previewSimulation(d, next);
    expect(next).toEqual(before); expect(preview.tick).toBe(next.tick); expect(preview.events.length).toBe(next.events.length);
    model(mesh).outlierThresholdPct = 50;
    s = stepSimulation(d, next);
    expect(s.nodes[mesh.id].meshEjected).toBe(true); expect(s.nodes[mesh.id].processed).toBe(0); expect(s.nodes[mesh.id].technology.attempts).toBe(0);
    model(service).capacity = 1000;
    s = stepSimulation(d, s);
    expect(s.nodes[mesh.id].meshEjected).toBe(false); near(s.nodes[mesh.id].completed, 250); near(s.summary!.completed, 250);
  });
  it("Vector query and upsert ports retain separate budgets and memory/dimension/breadth costs affect actual accepted flows", () => {
    const d = materializeScenario("vector-query-index"), vector = find(d, "vector-db"), client = find(d, "client"), producer = find(d, "event-producer");
    let s = stepSimulation(d), r = s.nodes[vector.id];
    near(r.technology.queryProcessed, 187.5); near(r.technology.indexProcessed, 250);
    vector.config.model = { queryCapacityRps: 50, upsertCapacityRps: 25 };
    s = stepSimulation(d); r = s.nodes[vector.id];
    near(r.processed, 75); near(r.rejected, 362.5); near(r.pressurePct, 1000); near(s.nodes[client.id].completed, 112.5); near(s.nodes[producer.id].completed, 25);
    near(r.inputAcceptance["query-in"], 50 / 187.5); near(r.inputAcceptance["index-in"], .1);
    Object.assign(model(vector), { dimensions: 3072, workingSetGb: 64, efSearch: 128 });
    s = stepSimulation(d); r = s.nodes[vector.id];
    near(r.technology.queryProcessed, 6.25); near(r.technology.indexProcessed, 6.25); near(r.technology.memoryUtilization, 2); near(r.latencyMs, 64);
  });
  it("CDC conserves captured changes, retained lag and overflow, distinguishes schema loss and preserves backlog during physical failure", () => {
    const d = materializeScenario("cdc-retention"), cdc = find(d, "cdc-connector"), client = find(d, "client");
    let s = stepSimulation(d), r = s.nodes[cdc.id];
    near(r.processed, 100); near(r.backlog, 150); near(r.technology.emitted, 99); near(r.technology.schemaRejected, 1);
    s = stepSimulation(d, s);
    near(s.nodes[cdc.id].backlog, 300);
    model(client).rate = 0;
    s = stepSimulation(d, s); r = s.nodes[cdc.id];
    near(r.offered, 0); near(r.processed, 100); near(r.backlog, 200);
    const committed = structuredClone(s), preview = previewSimulation(d, s);
    expect(s).toEqual(committed); near(preview.nodes[cdc.id].backlog, 200); near(preview.nodes[cdc.id].technology.lag, 200);
    model(client).rate = 250;
    modelCommand(s, d, "crash", [cdc.id]);
    s = stepSimulation(d, s); r = s.nodes[cdc.id];
    near(r.backlog, 200); near(r.technology.emitted, 0); near(r.technology.unavailableRejected, 250); near(r.technology.overflow, 0);
    modelCommand(s, d, "restore-all");
    for (let i = 0; i < 3; i++) s = stepSimulation(d, s);
    expect(s.nodes[cdc.id].technology.emitted).toBeGreaterThan(0);
    model(cdc).walLagLimit = 10;
    s = stepSimulation(d); r = s.nodes[cdc.id];
    near(r.processed + r.backlog + r.technology.overflow, 250); near(r.technology.overflow, 140); near(r.admitted, 110); near(r.rejected, 140);
    const shrink = cdcCapture({ ...config(cdc), walLagLimit: 10 }, 0, 500, 100);
    near(shrink.captured + shrink.lag + shrink.overflow, 500); near(shrink.overflow, 390);
  });
});
