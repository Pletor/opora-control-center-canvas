// Cloudové profily simulace (prototyp `cloud-profiles.mjs`): parametry profilů, složení výchozích hodnot z katalogu S4
// (`catalog-cloud.ts`, `sourceDefaults`), rozpočet kapacity a výpočty edge cache a load balanceru. Data katalogu se
// neduplikují, jen se čtou.
import { cloudCatalog } from "../../logic/catalog-cloud";
import type { ComponentType } from "../../logic/model-types";
import { cacheParameters } from "./cache-model";
import { gatewayParameters } from "./gateway-model";
import { monitoringParameters } from "./monitoring-model";
import { objectStoreBudget, objectStoreParameters } from "./object-store-model";
import { partitionedBudget, partitionedParameters } from "./partitioned-model";
import { poolBudget, poolParameters } from "./pool-model";
import { serverlessBudget, serverlessParameters, serverlessScaleParameters } from "./serverless-model";
import type { ModelConfig, ParameterTable } from "./simulation-types";
import { workflowParameters } from "./workflow-model";

export const CLOUD_VERSION = "cloud-model/7";
export const cloudParameters: ParameterTable = {
  edgeCapacityRps: { label: "Edge request budget / step", min: 0, max: 1e9 },
  edgeHitRate: { label: "Configured edge hit ratio", min: 0, max: 1 },
  originShieldRate: { label: "Shield hit ratio on edge misses", min: 0, max: 1 },
  staleWhileRevalidateSeconds: { label: "Stale fallback window (model seconds)", min: 0, max: 86400 },
  capacityRps: { label: "Balancer request budget / step", min: 0, max: 1e9 },
  healthProbeRps: { label: "Active health probe budget / model step", min: 0, max: 1e6 },
};
Object.assign(cloudParameters, objectStoreParameters, poolParameters, cacheParameters, gatewayParameters, monitoringParameters, workflowParameters, serverlessParameters, serverlessScaleParameters);
// Starší profily si nechávají sdílená omezení parametrů; pravidla nového profilu platí jen v jeho rozsahu.
for (const [key, rule] of Object.entries(partitionedParameters)) if (!cloudParameters[key]) cloudParameters[key] = rule;

const byId = new Map(cloudCatalog.map((c) => [c.id, c]));
export const cloudDefinition = (type: string | undefined): ComponentType | undefined => (type === undefined ? undefined : byId.get(type));
export const cloudProfile = (type: string | undefined): string | undefined => cloudDefinition(type)?.cloudProfile;

export function cloudConfig(type: string, settings: ModelConfig = {}): ModelConfig | null {
  const definition = cloudDefinition(type);
  return definition ? { ...definition.sourceDefaults, ...settings } : null;
}

export function cloudParameterKeys(type: string): string[] {
  const profile = cloudProfile(type);
  return profile === "partitioned-store" ? Object.keys(partitionedParameters) : profile === "object-store" ? Object.keys(objectStoreParameters)
    : profile === "connection-pool" ? Object.keys(poolParameters) : profile === "cache" ? Object.keys(cacheParameters)
    : profile === "serverless-function" ? [...Object.keys(serverlessParameters), ...Object.keys(serverlessScaleParameters)]
    : profile === "workflow" ? Object.keys(workflowParameters) : profile === "observability" ? Object.keys(monitoringParameters)
    : profile === "gateway" ? Object.keys(gatewayParameters)
    : profile === "edge-cache" ? ["edgeCapacityRps", "edgeHitRate", "originShieldRate", "staleWhileRevalidateSeconds", "serviceLatencyMs"]
    : profile === "load-balancer" ? ["capacityRps", "healthProbeRps", "serviceLatencyMs"] : [];
}

export function cloudBudget(type: string, c: ModelConfig): { capacity: number; replicas: number; latencyMs: number } {
  const profile = cloudProfile(type);
  if (profile === "partitioned-store") return { capacity: partitionedBudget(c).capacity, replicas: 1, latencyMs: c.serviceLatencyMs };
  if (profile === "object-store") return { capacity: objectStoreBudget(c).capacity, replicas: 1, latencyMs: c.firstByteLatencyMs };
  if (profile === "connection-pool") return { capacity: poolBudget(c).capacity, replicas: 1, latencyMs: c.readLatencyMs };
  if (profile === "serverless-function") { const b = serverlessBudget(c); return { capacity: b.capacity, replicas: 1, latencyMs: b.meanDurationMs }; }
  return {
    capacity: profile === "cache" ? c.capacityRps : profile === "workflow" ? c.dispatchRps : profile === "observability" ? c.ingestCapacityRps : profile === "gateway" ? 1e9
      : profile === "load-balancer" ? c.capacityRps : c.edgeCapacityRps,
    replicas: profile === "observability" ? c.replicaCount : 1,
    latencyMs: profile === "workflow" ? Math.max(.1, c.externalDelayMs) : profile === "observability" ? 5 : profile === "gateway" ? c.baseLatencyMs : c.serviceLatencyMs,
  };
}

export function edgeCacheMetrics(c: ModelConfig, processed: number, previous: ModelConfig = {}): ModelConfig {
  const edgeHits = processed * c.edgeHitRate, shieldHits = (processed - edgeHits) * c.originShieldRate;
  return { modelVersion: CLOUD_VERSION, edgeHits, shieldHits, originRequests: Math.max(0, processed - edgeHits - shieldHits), lastOriginSuccessTick: previous.technology?.lastOriginSuccessTick ?? null };
}

export function completeEdgeCache(c: ModelConfig, metrics: ModelConfig, { tick, processed, originConnected, originSuccess }: { tick: number; processed: number; originConnected: boolean; originSuccess: number }): ModelConfig {
  const success = originConnected ? Math.max(0, Math.min(1, originSuccess)) : 0;
  const lastOriginSuccessTick = metrics.originRequests > 0 && success >= 1 - 1e-9 ? tick : metrics.lastOriginSuccessTick;
  const staleAgeSeconds = lastOriginSuccessTick === null ? null : Math.max(0, tick - lastOriginSuccessTick);
  const staleEligible = staleAgeSeconds !== null && staleAgeSeconds > 0 && staleAgeSeconds <= c.staleWhileRevalidateSeconds;
  const staleServed = staleEligible ? metrics.originRequests * (1 - success) : 0, completed = metrics.edgeHits + metrics.shieldHits + metrics.originRequests * success + staleServed;
  return { ...metrics, lastOriginSuccessTick, staleAgeSeconds, staleServed, originConnected, originSuccess: success, completed, success: processed ? Math.max(0, Math.min(1, completed / processed)) : 1 };
}

export type BalanceTarget = { edgeId: string; nodeId: string; available: boolean };

/** Rovnoměrné podíly mezi cíli, jejichž poslední aktivní sonda neselhala; neznámé cíle zůstávají způsobilé. */
export function balanceTargets(c: ModelConfig, targets: BalanceTarget[], old: ModelConfig = {}, preview = false, failed = false): ModelConfig {
  const health: Record<string, boolean | null> = Object.fromEntries(targets.map((t) => [t.nodeId, old.health?.[t.nodeId] ?? null]));
  const unique = [...new Set(targets.map((t) => t.nodeId))], raw = (old.probeCredit || 0) + c.healthProbeRps;
  const count = !preview && !failed ? Math.min(unique.length, Math.floor(raw)) : 0, cursor = unique.length ? (old.probeCursor || 0) % unique.length : 0;
  for (let n = 0; n < count; n++) { const id = unique[(cursor + n) % unique.length]; health[id] = targets.find((t) => t.nodeId === id)!.available; }
  const eligible = targets.filter((t) => health[t.nodeId] !== false), weights = Object.fromEntries(targets.map((t) => [t.edgeId, eligible.includes(t) ? 1 / eligible.length : 0]));
  return {
    modelVersion: CLOUD_VERSION, health, weights, probeCredit: preview || failed ? (old.probeCredit || 0) : raw - Math.floor(raw),
    probeCursor: preview || failed ? cursor : unique.length ? (cursor + count) % unique.length : 0, probes: preview ? (old.probes || 0) : count,
    routable: eligible.length, excluded: targets.length - eligible.length, unknown: unique.filter((id) => health[id] === null).length, targets: targets.length,
  };
}
