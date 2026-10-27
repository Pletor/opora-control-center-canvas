// Vlastní deterministický tekutinový model cache (prototyp `cache-model.mjs`). Pozorované příklady omezují rekonstrukci;
// pravidla nespouštějí Redis ani netvrdí, že jde o původní algoritmus Studia.
import { checkParameters, type KernelOptions } from "./parameter-check";
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const CACHE_VERSION = "cache-model/1";
export const cacheParameters: ParameterTable = {
  capacityRps: { label: "Configured cache checks / model step", min: 0, max: 1e9 },
  cacheHitRate: { label: "Configured cache hit rate", min: 0, max: 1, step: .01 },
  ttlSeconds: { label: "TTL (model seconds)", min: 0, max: 1e9 },
  memoryLimitMb: { label: "Memory limit (MB)", min: 0, max: 1e9 },
  workingSetMb: { label: "Working set (MB)", min: 0, max: 1e9 },
  serviceLatencyMs: { label: "Cache service processing time (model ms)", min: 1, max: 1e6 },
  partitionCount: { label: "Logical cache partitions", min: 1, max: 1000000 },
  replicationFactor: { label: "Configured cache replication factor", min: 0, max: 1000 },
  evictionPolicy: { label: "Eviction policy", enum: ["lru", "ttl"] },
  failedNodeCount: { label: "Configured failed cache nodes", min: 0, max: 1e9 },
  failoverTicks: { label: "Configured failover steps", min: 0, max: 1000000 },
  hotKeyShare: { label: "Configured hot-key share", min: 0, max: 1, step: .01 },
  rebalanceRps: { label: "Configured rebalance budget / model step", min: 0, max: 1e9 },
};
export const cacheIntegers = ["ttlSeconds", "memoryLimitMb", "partitionCount", "replicationFactor", "failedNodeCount", "failoverTicks"];

export function cacheHitProfile(c: ModelConfig) {
  checkParameters(c, cacheParameters, cacheIntegers, "cache");
  const memoryPressure = Math.max(0, (c.workingSetMb - Math.max(1, c.memoryLimitMb)) / Math.max(1, c.workingSetMb));
  // Vlastní ohraničená křivka shodná s pozorovanými vzorky TTL 0/1/30/60/300 a paměti; konečná množina pozorování
  // nedokazuje původní vzorec.
  const memoryFactor = 1 - .6 * memoryPressure, ttlFactor = Math.max(.35, Math.min(1, c.ttlSeconds / 60));
  return { memoryPressure, memoryFactor, ttlFactor, effectiveHitRate: c.cacheHitRate * memoryFactor * ttlFactor };
}

export function evaluateCache(c: ModelConfig, offered: number, { capacityFactor = 1, failed = false }: KernelOptions = {}) {
  const profile = cacheHitProfile(c);
  if (!Number.isFinite(offered) || offered < 0 || !Number.isFinite(capacityFactor) || capacityFactor < 0 || capacityFactor > 1) throw new RangeError("Invalid cache workload");
  const capacity = c.capacityRps * capacityFactor, processed = failed ? 0 : Math.min(offered, capacity), hits = processed * profile.effectiveHitRate;
  const misses = processed - hits, fallback = offered - processed;
  const averagePartitionRps = processed / c.partitionCount, hottestPartitionRps = averagePartitionRps * (1 + c.hotKeyShare * (c.partitionCount - 1));
  return {
    modelVersion: CACHE_VERSION, ...profile, capacity, offered, processed, hits, misses, fallback, rejected: fallback, originRequests: misses + fallback,
    latencyMs: capacityFactor ? c.serviceLatencyMs / capacityFactor : c.serviceLatencyMs,
    accounting: {
      averagePartitionRps, hottestPartitionRps, skewRejected: Math.max(0, hottestPartitionRps - Math.max(1, c.capacityRps) / c.partitionCount),
      availableReplicas: Math.max(0, c.replicationFactor - c.failedNodeCount), failoverWait: c.failedNodeCount * c.failoverTicks,
      movedKeys: Math.min(processed, c.rebalanceRps), evictions: c.evictionPolicy === "lru" ? misses : 0, expirations: c.evictionPolicy === "ttl" ? misses : 0,
    },
    // Ponechaná definice, výslovně netvrdí, že je modelovaný životní cyklus clusteru.
    clusterLifecycleModeled: false, logicalPartitions: c.partitionCount, replicationFactor: c.replicationFactor, failedNodeCount: c.failedNodeCount,
    evictionPolicy: c.evictionPolicy,
  };
}
