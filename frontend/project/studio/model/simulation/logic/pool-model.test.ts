// Převedeno z prototypu `test/pool-model.test.mjs`; vynecháno: nic. Pozorování (profile `connection-pool`) jsou konstanty
// z `analysis/evidence/extended-catalog-observations.json` (items[].defaults pro aws-rds, gcp-cloud-sql, aliyun-polardb).
import { describe, expect, it } from "vitest";
import { evaluatePool, poolBudget } from "./pool-model";

const common = { readRatio: .8, isolationLevel: "read-committed", stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2 };
const items: { id: string; defaults: Record<string, any> }[] = [
  { id: "aws-rds", defaults: { ...common, readCapacityRps: 24000, writeCapacityTps: 12000, maxConnections: 3000, readLatencyMs: 12, writeLatencyMs: 22, lockContention: .03 } },
  { id: "gcp-cloud-sql", defaults: { ...common, readCapacityRps: 22000, writeCapacityTps: 11000, maxConnections: 2500, readLatencyMs: 14, writeLatencyMs: 24, lockContention: .03 } },
  { id: "aliyun-polardb", defaults: { ...common, readCapacityRps: 28000, writeCapacityTps: 14000, maxConnections: 3200, readLatencyMs: 10, writeLatencyMs: 20, lockContention: .02 } },
];
const base = items[0].defaults;
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-8);

describe("pool-model", () => {
  it("Three provider SQL250 baselines preserve their exact read/commit/retry volumes and fractional occupancy", () => {
    for (const item of items) {
      const r = evaluatePool(item.defaults, 250), writes = 50 * (1 - item.defaults.lockContention);
      near(r.readServed, 200); near(r.writeCommitted, writes); near(r.processed, 200 + writes); near(r.writeRetries, 50 - writes);
      near(r.activeConnections, (200 * item.defaults.readLatencyMs + 50 * item.defaults.writeLatencyMs) / 1000);
      near(r.outputs["replication-out"], writes); near(r.outputs["sql-out"], 200 + writes); near(r.processed + r.rejected, 250);
    }
    near(evaluatePool(base, 250).latencyMs, 12 / (1 - 200 / 24000));
  });
  it("Read100/write10 ceilings independently yield109.7 rather than a falsely uniform mixed ceiling", () => {
    const r = evaluatePool({ ...base, readCapacityRps: 100, writeCapacityTps: 10 }, 250);
    near(r.readServed, 100); near(r.writeAdmitted, 10); near(r.writeCommitted, 9.7); near(r.processed, 109.7); near(r.rejected, 140.3);
    near(r.connectionRejected, 140); near(r.writeRetries, .3); near(r.activeConnections, 1.42); near(r.pressurePct, 500); near(r.latencyMs, 12000);
  });
  it("One physical connection scales both admitted classes by occupancy and preserves71 served at250offered", () => {
    const r = evaluatePool({ ...base, maxConnections: 1 }, 250);
    near(r.occupancy, 3.5); near(r.scale, 1 / 3.5); near(r.readServed, 200 / 3.5); near(r.writeAdmitted, 50 / 3.5); near(r.processed, 71); near(r.rejected, 179);
    near(r.activeConnections, 1); near(r.utilization, 1); near(r.latencyMs, 12000); near(r.capacity, 1000 / 14); expect(r.limiter).toBe("connection-pool");
  });
  it("Isolation multipliers produce deterministic write losses without rescheduling or double-counting reads", () => {
    for (const [isolationLevel, multiplier] of [["read-committed", 1], ["repeatable-read", 1.25], ["serializable", 1.6]] as const) {
      const r = evaluatePool({ ...base, isolationLevel, lockContention: .5 }, 250);
      near(r.writeRetries, 25 * multiplier); near(r.writeCommitted, 50 - 25 * multiplier); near(r.readServed, 200); near(r.processed + r.writeRetries, 250); near(r.connectionRejected, 0);
    }
  });
  it("Capacity presentation uses weighted guarded durations while node latency uses the read service kernel", () => {
    const c = { ...base, readLatencyMs: 100, writeLatencyMs: 100 }, r = evaluatePool(c, 250);
    near(r.processed, 248.5); near(r.activeConnections, 25); near(r.latencyMs, 100 / (1 - 200 / 24000)); near(poolBudget({ ...base, maxConnections: 1 }).weightedMs, 14);
    const zeros = evaluatePool({ ...base, readLatencyMs: 0, writeLatencyMs: 0 }, 250);
    near(zeros.weightedMs, 1); near(zeros.activeConnections, .25); near(zeros.latencyMs, 0);
  });
  it("Zero budgets and pure read/write extremes remain finite and conserve offered units without overflow", () => {
    for (const readRatio of [0, .2, .8, 1]) for (const readCapacityRps of [0, 10, 1000]) for (const writeCapacityTps of [0, 10, 1000]) for (const offered of [0, .5, 250]) {
      const r = evaluatePool({ ...base, readRatio, readCapacityRps, writeCapacityTps }, offered);
      near(r.processed + r.rejected, offered); near(r.readServed + r.writeCommitted, r.processed); near(r.connectionRejected + r.writeRetries, r.rejected);
      expect(r.activeConnections).toBeLessThanOrEqual(base.maxConnections);
      expect(Object.values(r).every((v) => typeof v !== "number" || Number.isFinite(v))).toBe(true);
      if (readCapacityRps + writeCapacityTps === 0) near(r.pressurePct, offered ? 1000 : 0);
    }
  });
  it("Own Slow budget and explicit failed flag never emit unavailable writes or recover lost prior work", () => {
    const c = { ...base, readCapacityRps: 100, writeCapacityTps: 10 }, slow = evaluatePool(c, 250, { capacityFactor: .2 }), failed = evaluatePool(c, 250, { failed: true });
    near(slow.readServed, 20); near(slow.writeCommitted, 1.94); near(slow.processed, 21.94); near(failed.processed, 0); near(failed.activeConnections, 0); near(failed.unavailable, 250);
    expect(failed.outputs).toEqual({}); near(evaluatePool(c, 250).processed, 109.7);
  });
  it("Definitions and results remain deterministic and pure; invalid finite bounds and enum values are rejected", () => {
    const before = structuredClone(base), r = evaluatePool(base, 250);
    for (let i = 0; i < 50; i++) expect(evaluatePool(base, 250)).toEqual(r);
    expect(base).toEqual(before);
    for (const patch of [{ readRatio: 2 }, { maxConnections: 0 }, { maxConnections: 1.5 }, { lockContention: .51 }, { isolationLevel: "unsafe" }, { writeLatencyMs: -1 }, { readLatencyMs: Infinity }])
      expect(() => evaluatePool({ ...base, ...patch }, 250)).toThrow(RangeError);
    for (const offered of [-1, NaN, Infinity]) expect(() => evaluatePool(base, offered)).toThrow(RangeError);
    for (const capacityFactor of [-1, NaN, 2]) expect(() => evaluatePool(base, 1, { capacityFactor })).toThrow(RangeError);
  });
});
