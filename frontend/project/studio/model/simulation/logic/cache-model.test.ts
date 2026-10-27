// Převedeno z prototypu `test/cache-model.test.mjs`; vynecháno: nic. Pozorování poskytovatelů (profile `cache`) jsou
// konstanty z `analysis/evidence/extended-catalog-observations.json` (items[].defaults pro aws-elasticache, gcp-memorystore, aliyun-tair).
import { describe, expect, it } from "vitest";
import { cacheHitProfile, evaluateCache } from "./cache-model";

const common = { ttlSeconds: 300, evictionPolicy: "lru", failedNodeCount: 0, failoverTicks: 2, serviceLatencyMs: 1, partitionCount: 16, replicationFactor: 2, stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2 };
const items: { id: string; defaults: Record<string, any> }[] = [
  { id: "aws-elasticache", defaults: { ...common, capacityRps: 65000, cacheHitRate: .85, memoryLimitMb: 2048, workingSetMb: 1024, hotKeyShare: .1, rebalanceRps: 8000 } },
  { id: "gcp-memorystore", defaults: { ...common, capacityRps: 60000, cacheHitRate: .84, memoryLimitMb: 2048, workingSetMb: 1024, partitionCount: 12, hotKeyShare: .1, rebalanceRps: 7000 } },
  { id: "aliyun-tair", defaults: { ...common, capacityRps: 75000, cacheHitRate: .88, memoryLimitMb: 4096, workingSetMb: 1536, hotKeyShare: .08, rebalanceRps: 9000 } },
];
const base = items[0].defaults;
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-9);

describe("cache-model", () => {
  it("Cache reconstruction preserves observed baseline provider hit fractions without rounding conserved fluid units", () => {
    const expected: Record<string, number> = { "aws-elasticache": 212.5, "gcp-memorystore": 210, "aliyun-tair": 220 };
    for (const item of items) {
      const r = evaluateCache(item.defaults, 250);
      near(r.hits, expected[item.id]); near(r.processed, 250); near(r.hits + r.misses + r.fallback, 250);
      near(r.originRequests, 250 - expected[item.id]); expect(r.clusterLifecycleModeled).toBe(false);
    }
  });
  it("Observed AWS memory512 and TTL0 samples constrain separate multiplicative hit factors", () => {
    near(evaluateCache({ ...base, memoryLimitMb: 512 }, 250).effectiveHitRate, .595);
    near(evaluateCache({ ...base, ttlSeconds: 0 }, 250).effectiveHitRate, .2975);
    near(evaluateCache({ ...base, memoryLimitMb: 512, ttlSeconds: 0 }, 250).effectiveHitRate, .20825);
    near(evaluateCache({ ...base, memoryLimitMb: 512, ttlSeconds: 0 }, 250).originRequests, 197.9375);
  });
  it("Additional independent source TTL1/30/60 and memory256 points constrain the initial interpolation", () => {
    for (const [ttlSeconds, hit] of [[1, .2975], [30, .425], [60, .85]]) near(evaluateCache({ ...base, ttlSeconds }, 250).effectiveHitRate, hit);
    near(evaluateCache({ ...base, memoryLimitMb: 256 }, 250).effectiveHitRate, .4675);
  });
  it("Capacity, Slow and Crash send actual lost lookups to fallback; misses are distinct from unavailable checks", () => {
    const c = { ...base, capacityRps: 100 }, r = evaluateCache(c, 250);
    near(r.processed, 100); near(r.hits, 85); near(r.misses, 15); near(r.fallback, 150); near(r.originRequests, 165);
    const slow = evaluateCache(c, 250, { capacityFactor: .2 });
    near(slow.processed, 20); near(slow.latencyMs, 5); near(slow.hits + slow.misses + slow.fallback, 250);
    const failed = evaluateCache(c, 250, { failed: true });
    near(failed.hits, 0); near(failed.misses, 0); near(failed.fallback, 250); near(failed.originRequests, 250);
  });
  it("Own interpolation is bounded, deterministic and pure across finite workloads and memory/TTL pressure", () => {
    for (const ttlSeconds of [0, 1, 30, 300, 1e9]) for (const memoryLimitMb of [0, 256, 512, 2048]) for (const offered of [0, .5, 250, 1e9]) {
      const c = { ...base, ttlSeconds, memoryLimitMb }, before = structuredClone(c), r = evaluateCache(c, offered);
      expect(c).toEqual(before); expect(evaluateCache(c, offered)).toEqual(r);
      expect(r.effectiveHitRate).toBeGreaterThanOrEqual(0); expect(r.effectiveHitRate).toBeLessThanOrEqual(1);
      near(r.hits + r.misses + r.fallback, offered);
      expect(Object.values(r).every((v) => typeof v !== "number" || Number.isFinite(v))).toBe(true);
    }
  });
  it("Unknown cluster algorithm is not invented from unchanged failed-node source examples", () => {
    for (const failedNodeCount of [0, 1, 16]) {
      const r = evaluateCache({ ...base, failedNodeCount }, 250);
      expect(r.clusterLifecycleModeled).toBe(false); expect(r.failedNodeCount).toBe(failedNodeCount); near(r.hits, 212.5);
    }
  });
  it("Distributed cache accounting fields change diagnostic quantities without inventing physical failover or reducing admitted work", () => {
    const c = { ...base, partitionCount: 4, hotKeyShare: .5, capacityRps: 100, replicationFactor: 2, failedNodeCount: 1, failoverTicks: 3, rebalanceRps: 20 };
    const r = evaluateCache(c, 250), a = r.accounting;
    near(a.averagePartitionRps, 25); near(a.hottestPartitionRps, 62.5); near(a.skewRejected, 37.5); near(a.availableReplicas, 1); near(a.failoverWait, 3);
    near(a.movedKeys, 20); near(a.evictions, 15); near(a.expirations, 0); near(r.processed, 100); near(r.originRequests, 165);
    const ttl = evaluateCache({ ...c, evictionPolicy: "ttl" }, 250);
    near(ttl.accounting.evictions, 0); near(ttl.accounting.expirations, 15); near(ttl.processed, 100); expect(ttl.clusterLifecycleModeled).toBe(false);
  });
  it("Observed distributed zero-memory and zero-working-set guards remain finite without changing the AI contract", () => {
    const empty = evaluateCache({ ...base, workingSetMb: 0, memoryLimitMb: 0 }, 250);
    near(empty.memoryPressure, 0); near(empty.effectiveHitRate, .85);
    const zeroMemory = evaluateCache({ ...base, memoryLimitMb: 0 }, 250);
    near(zeroMemory.memoryPressure, 1023 / 1024); near(zeroMemory.effectiveHitRate, .85 * (1 - .6 * 1023 / 1024));
  });
  it("Invalid cache definitions and runtime values fail before calculating apparent results", () => {
    for (const patch of [{ capacityRps: -1 }, { cacheHitRate: 2 }, { workingSetMb: -1 }, { ttlSeconds: 1.5 }, { evictionPolicy: "random" }, { memoryLimitMb: NaN }, { partitionCount: Infinity }])
      expect(() => cacheHitProfile({ ...base, ...patch })).toThrow(RangeError);
    for (const offered of [-1, NaN, Infinity]) expect(() => evaluateCache(base, offered)).toThrow(RangeError);
    for (const capacityFactor of [-1, 2, NaN]) expect(() => evaluateCache(base, 1, { capacityFactor })).toThrow(RangeError);
  });
});
