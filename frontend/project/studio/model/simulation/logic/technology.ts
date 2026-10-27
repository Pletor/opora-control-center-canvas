// Výpočetní část technologických typů (prototyp `technology.mjs`): rozpočty a metriky AI inference, identity, service
// mesh, vektorové DB a CDC. Výchozí parametry, meze a katalog jsou data S4 v `model/logic/catalog-technology.ts`;
// tady se jen čtou. Deterministická rekonstrukce, žádné skutečné LLM, identita, sidecar, index ani WAL.
import { technologyDefaults, technologyIntegers, technologyParameters } from "../../logic/catalog-technology";
import type { ModelConfig } from "./simulation-types";

export const technologyVersion = "technology-model/2";
export { technologyIntegers, technologyParameters };
export const aiDefaults = technologyDefaults["ai-inference"];
export const authDefaults = technologyDefaults["auth-provider"];
export const meshDefaults = technologyDefaults["service-mesh"];
export const vectorDefaults = technologyDefaults["vector-db"];
export const cdcDefaults = technologyDefaults["cdc-connector"];

export const technologyParameterKeys = (type: string): string[] => Object.keys(technologyDefaults[type] || {});

export function technologyConfig(type: string, settings: ModelConfig = {}): ModelConfig | null {
  const defaults = technologyDefaults[type];
  if (!defaults) return null;
  return { ...defaults, crashAfterTicks: 3, ...settings };
}

export function technologyBudget(type: string, c: ModelConfig): { capacity: number; latencyMs: number } {
  if (type === "ai-inference") return aiBudget(c);
  if (type === "service-mesh") return { capacity: c.proxyCapacityRps, latencyMs: c.serviceLatencyMs + c.mtlsOverheadMs };
  if (type === "vector-db") { const b = vectorBudget(c); return { capacity: b.query + b.upsert, latencyMs: b.latencyMs }; }
  if (type === "cdc-connector") return { capacity: c.captureCapacityRps, latencyMs: c.serviceLatencyMs + c.transformMs };
  return { capacity: c.verifyCapacityRps, latencyMs: c.serviceLatencyMs + (1 - c.tokenCacheHitRate + 2 * c.mfaChallengeShare) * c.jwksLatencyMs };
}

export function authVerification(c: ModelConfig, verified: number): ModelConfig {
  return {
    modelVersion: technologyVersion, verified, policyRejected: verified * c.invalidTokenRejectRate, accepted: verified * (1 - c.invalidTokenRejectRate),
    tokenCacheHits: verified * c.tokenCacheHitRate, jwksRequests: verified * (1 - c.tokenCacheHitRate), mfaChallenges: verified * c.mfaChallengeShare,
  };
}

export function aiBudget(settings: ModelConfig): { capacity: number; latencyMs: number; memoryFactor: number } {
  const c = { ...aiDefaults, ...settings }, miss = 1 - c.semanticCacheHitRate, memoryFactor = Math.min(1, c.kvCacheLimitMb / c.workingSetMb);
  return { capacity: miss ? c.maxTokensPerSec * memoryFactor / (c.avgTokensPerRequest * miss) : Infinity, latencyMs: c.ttftMs + miss * c.serviceLatencyMs / memoryFactor, memoryFactor };
}

export function aiMetrics(settings: ModelConfig, processed: number): ModelConfig {
  const c = { ...aiDefaults, ...settings }, decodedRequests = processed * (1 - c.semanticCacheHitRate);
  return { modelVersion: technologyVersion, tokens: decodedRequests * c.avgTokensPerRequest, semanticHits: processed * c.semanticCacheHitRate, decodedRequests, kvUtilization: c.workingSetMb / c.kvCacheLimitMb, ttftMs: c.ttftMs };
}

export function meshDecision(c: ModelConfig, old: ModelConfig = {}, preview = false): { modelVersion: string; retryRatio: number; ejected: boolean; priorFailurePct: number } {
  const failure = Math.max(0, Math.min(1, 1 - (old.dependencySuccess ?? 1))), retryRatio = Math.min(c.retryBudgetPct / 100, failure);
  const ejected = preview ? Boolean(old.meshEjected) : Boolean(!old.meshEjected && old.offered > 0 && failure > 0 && c.outlierThresholdPct > 0 && failure * 100 >= c.outlierThresholdPct);
  return { modelVersion: technologyVersion, retryRatio, ejected, priorFailurePct: failure * 100 };
}

export function vectorBudget(c: ModelConfig) {
  const memoryFactor = Math.min(1, c.indexMemoryLimitGb / c.workingSetGb), dimensionFactor = c.dimensions / 1536, breadthFactor = c.efSearch / 64;
  return { query: c.queryCapacityRps * memoryFactor / (dimensionFactor * breadthFactor), upsert: c.upsertCapacityRps * memoryFactor / dimensionFactor, memoryFactor, latencyMs: c.serviceLatencyMs * dimensionFactor * breadthFactor / memoryFactor };
}

export function vectorPressure(c: ModelConfig, byPort: Record<string, number>, slow = 1): number {
  const b = vectorBudget(c), pressure = (offered: number, budget: number) => (budget ? offered / budget * 100 : offered ? 100000 : 0);
  return Math.max(pressure(byPort["query-in"] || 0, b.query / slow), pressure(byPort["index-in"] || 0, b.upsert / slow));
}

export function vectorEvaluate(c: ModelConfig, byPort: Record<string, number>, capacity: number, slow = 1): ModelConfig {
  const b = vectorBudget(c), queryOffered = byPort["query-in"] || 0, indexOffered = byPort["index-in"] || 0, q = Math.min(queryOffered, b.query / slow), i = Math.min(indexOffered, b.upsert / slow);
  const scale = q + i ? Math.min(1, capacity / (q + i)) : 0;
  return { modelVersion: technologyVersion, queryProcessed: q * scale, indexProcessed: i * scale, queryOffered, indexOffered, memoryUtilization: c.workingSetGb / c.indexMemoryLimitGb };
}

export function cdcCapture(c: ModelConfig, offered: number, oldBacklog: number, capacity: number, failed = false): ModelConfig {
  if (failed) return { modelVersion: technologyVersion, captured: 0, schemaRejected: 0, emitted: 0, lag: oldBacklog, overflow: 0, unavailableRejected: offered, admissionRejected: offered, admitted: 0 };
  const captured = Math.min(oldBacklog + offered, capacity, c.snapshotBatchSize), retained = oldBacklog + offered - captured, lag = Math.min(c.walLagLimit, retained);
  const overflow = Math.max(0, retained - lag), schemaRejected = captured * c.schemaErrorRate;
  return { modelVersion: technologyVersion, captured, schemaRejected, emitted: captured - schemaRejected, lag, overflow, unavailableRejected: 0, admissionRejected: overflow, admitted: Math.max(0, offered - overflow) };
}
