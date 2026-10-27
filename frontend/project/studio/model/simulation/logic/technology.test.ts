// Převedeno z prototypu `test/technology.test.mjs`; vynecháno: nic (export/import projektu nahrazen JSON round-tripem modelu).
// Důkazy `analysis/evidence/extended-catalog-observations.json` se za běhu nečtou, jejich hodnoty jsou níže jako konstanty.
import { describe, expect, it } from "vitest";
import { connectionError } from "../../logic/model-rules";
import { emptyStudioModel } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { config } from "./simulation-config";
import { modelCommand, stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";
import { aiBudget, aiDefaults, authDefaults } from "./technology";

/** `extended-catalog-observations.json`, `items[id="ai-inference"].defaults`. */
const AI_SOURCE_DEFAULTS = {
  maxTokensPerSec: 400000, avgTokensPerRequest: 400, ttftMs: 45, kvCacheLimitMb: 24576, workingSetMb: 16384, semanticCacheHitRate: 0.25, serviceLatencyMs: 120,
  stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2,
  minInstances: 1, maxInstances: 1, autoscaleTargetPct: 70, autoscaleScaleDownTicks: 3,
};
/** `extended-catalog-observations.json`, `items[id="auth-provider"].defaults`. */
const AUTH_SOURCE_DEFAULTS = {
  verifyCapacityRps: 25000, tokenCacheHitRate: 0.85, jwksLatencyMs: 18, invalidTokenRejectRate: 0.02, mfaChallengeShare: 0.05, serviceLatencyMs: 3,
  stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2,
  minInstances: 1, maxInstances: 1, autoscaleTargetPct: 70, autoscaleScaleDownTicks: 3,
};

const model = (n: { config: Record<string, unknown> }) => n.config.model as Record<string, any>;
const near = (a: number, b: number, eps: number) => expect(Math.abs(a - b)).toBeLessThan(eps);
const roundtrip = <T>(m: T): T => validateSimulationModel(JSON.parse(JSON.stringify(m)));

describe("technology", () => {
  it("AI defaults and port signature agree with independent retained source observations", () => {
    for (const [key, value] of Object.entries(aiDefaults)) expect(value, key).toBe((AI_SOURCE_DEFAULTS as Record<string, number>)[key]);
    const d = emptyStudioModel("ai-ports"), client = createSimulationNode("client"), gate = createSimulationNode("api-gateway"), ai = createSimulationNode("ai-inference");
    d.nodes.push(client, gate, ai);
    expect(connectionError(d, { nodeId: client.id, portId: "http-out" }, { nodeId: ai.id, portId: "http-in" })).toMatch(/Role/);
    expect(connectionError(d, { nodeId: gate.id, portId: "http-out" }, { nodeId: ai.id, portId: "http-in" })).toBeNull();
    expect(roundtrip(d)).toEqual(d);
  });

  it("AI graph computes token units, cache hits, saturation and memory backpressure without random metrics", () => {
    const d = materializeScenario("ai-token-budget"), ai = d.nodes.find((n) => n.type === "ai-inference")!;
    const client = d.nodes.find((n) => n.type === "client")!, gate = d.nodes.find((n) => n.type === "api-gateway")!;
    let s = stepSimulation(d), r = s.nodes[ai.id];
    expect(r.processed).toBe(250);
    expect(r.technology.tokens).toBe(75000);
    expect(r.technology.semanticHits).toBe(62.5);
    expect(s.summary!.completed).toBe(250);
    model(client).rate = 5000;
    Object.assign(model(gate), { capacity: 100000, concurrency: 10000 });
    s = stepSimulation(d); r = s.nodes[ai.id];
    near(r.technology.tokens, 400000, .001);
    near(r.capacity, 1333.3333333333, .001);
    expect(r.rejected).toBeGreaterThan(3000);
    ai.config.model = { workingSetMb: 49152 };
    s = stepSimulation(d); r = s.nodes[ai.id];
    near(r.capacity, 666.6666666667, .001);
    expect(r.technology.kvUtilization).toBe(2);
    near(r.technology.tokens, 200000, .001);
    ai.config.model = { semanticCacheHitRate: 1, maxTokensPerSec: 0 };
    s = stepSimulation(d); r = s.nodes[ai.id];
    expect(r.technology.tokens).toBe(0);
    expect(r.technology.semanticHits).toBe(r.processed);
    expect(Number.isFinite(r.capacity)).toBe(true);
    expect(Number.isFinite(config(ai).latencyMs)).toBe(true);
    expect(aiBudget(model(ai)).latencyMs).toBe(45);
  });

  it("AI planned definition roundtrip is deterministic and manual outage/restore changes actual graph throughput", () => {
    const d = materializeScenario("ai-token-budget"), ai = d.nodes.find((n) => n.type === "ai-inference")!;
    const restored = roundtrip(d);
    let a, b;
    for (let i = 0; i < 12; i++) { a = stepSimulation(d, a); b = stepSimulation(restored, b); expect(a).toEqual(b); }
    modelCommand(a!, d, "crash", [ai.id]);
    a = stepSimulation(d, a);
    expect(a.nodes[ai.id].technology.tokens).toBe(0);
    expect(a.summary!.completed).toBe(0);
    modelCommand(a, d, "restore-all");
    for (let i = 0; i < 3; i++) a = stepSimulation(d, a);
    expect(a.nodes[ai.id].processed).toBe(250);
    expect(a.summary!.completed).toBe(250);
  });

  it("Auth uses observed defaults and deterministic verification, invalid-token rejection and cache accounting", () => {
    for (const [key, value] of Object.entries(authDefaults)) expect(value).toBe((AUTH_SOURCE_DEFAULTS as Record<string, number>)[key]);
    const d = materializeScenario("auth-admission"), auth = d.nodes.find((n) => n.type === "auth-provider")!;
    let s = stepSimulation(d), r = s.nodes[auth.id];
    expect(r.offered).toBe(250);
    expect(r.admitted).toBe(245);
    expect(r.rejected).toBe(5);
    expect(r.technology.verified).toBe(250);
    expect(r.technology.tokenCacheHits).toBe(212.5);
    near(r.technology.jwksRequests, 37.5, 1e-9);
    expect(r.technology.mfaChallenges).toBe(12.5);
    expect(s.summary!.completed).toBe(245);
    near(r.latencyMs, 7.5, 1e-9);
    auth.config.model = { invalidTokenRejectRate: 1 };
    s = stepSimulation(d); r = s.nodes[auth.id];
    expect(r.processed).toBe(0);
    expect(r.rejected).toBe(250);
    expect(s.summary!.completed).toBe(0);
    expect(r.technology.verified).toBe(250);
    auth.config.model = { verifyCapacityRps: 100 };
    s = stepSimulation(d); r = s.nodes[auth.id];
    expect(r.technology.verified).toBe(100);
    expect(r.processed).toBe(98);
    expect(r.rejected).toBe(152);
    expect(s.summary!.completed).toBe(98);
    expect(r.admitted + r.rejected).toBe(r.offered);
  });

  it("Auth upstream admission and downstream failure remain separate through import and recovery", () => {
    const d = materializeScenario("auth-admission"), auth = d.nodes.find((n) => n.type === "auth-provider")!, service = d.nodes.find((n) => n.type === "service")!;
    const copy = roundtrip(d);
    expect(copy).toEqual(d);
    let s = stepSimulation(d);
    modelCommand(s, d, "crash", [service.id]);
    s = stepSimulation(d, s);
    expect(s.nodes[auth.id].technology.accepted).toBe(245);
    expect(s.nodes[auth.id].completed).toBe(0);
    expect(s.summary!.completed).toBe(0);
    modelCommand(s, d, "restore-all");
    for (let i = 0; i < 3; i++) s = stepSimulation(d, s);
    expect(s.summary!.completed).toBe(245);
    let a, b;
    for (let i = 0; i < 10; i++) { a = stepSimulation(d, a); b = stepSimulation(copy, b); expect(a).toEqual(b); }
  });
});
