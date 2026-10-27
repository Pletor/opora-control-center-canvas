// Převedeno z prototypu `test/partitioned-model.test.mjs`; vynecháno: nic. Pozorování (profile `partitioned-store`) jsou konstanty
// z `analysis/evidence/extended-catalog-observations.json` (items[].defaults pro aws-dynamodb, gcp-bigtable, aliyun-tablestore).
import { describe, expect, it } from "vitest";
import { evaluatePartitioned, partitionedBudget } from "./partitioned-model";

const common = { partitionCount: 16, replicationFactor: 3, consistencyMode: "quorum", conditionalConflictRate: .01, idAllocationMode: "hash", allocationRangeSize: 1000, snapshotIntervalTicks: 10, stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2 };
const items: { id: string; defaults: Record<string, any> }[] = [
  { id: "aws-dynamodb", defaults: { ...common, capacityRps: 40000, readRatio: .8, hotKeyShare: .1, serviceLatencyMs: 5 } },
  { id: "gcp-bigtable", defaults: { ...common, capacityRps: 45000, readRatio: .75, hotKeyShare: .08, serviceLatencyMs: 6 } },
  { id: "aliyun-tablestore", defaults: { ...common, capacityRps: 42000, readRatio: .8, hotKeyShare: .1, serviceLatencyMs: 6 } },
];
const base = items[0].defaults;
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

describe("partitioned-model", () => {
  it("Three provider baselines separate admitted records, diagnostic mixes, CAS and CDC without claiming durability", () => {
    for (const i of items) {
      const before = structuredClone(i.defaults), r = evaluatePartitioned(i.defaults, 500);
      near(r.processed, 500); near(r.conditionalAccepted, 445.5); near(r.outputs["cdc-out"], 445.5); near(r.outputs["telemetry-out"], 500);
      near(r.hottestPartitionRps, i.id === "gcp-bigtable" ? 68.75 : 78.125);
      expect(r.partitionLifecycleModeled).toBe(false); expect(r.durableLogVerified).toBe(false);
      expect(i.defaults).toEqual(before); expect(evaluatePartitioned(i.defaults, 500)).toEqual(r);
    }
    const r = evaluatePartitioned(base, 500);
    near(r.readDemand, 400); near(r.writeDemand, 300); near(r.readServed, 400); near(r.writeAdmitted, 100 / 3);
    expect(r.readServed + r.writeAdmitted).not.toBe(r.processed);
  });
  it("Configured100 capacity yields observed independent AWS and GCP intake and CDC values", () => {
    const aws = evaluatePartitioned({ ...base, capacityRps: 100 }, 500);
    near(aws.capacity, 100 / 1.1); near(aws.processed, 100 / 1.1); near(aws.rejected, 500 - 100 / 1.1); near(aws.outputs["cdc-out"], 81); near(aws.pressurePct, 550); near(aws.latencyMs, 5000);
    const gcp = evaluatePartitioned({ ...items[1].defaults, capacityRps: 100 }, 500);
    near(gcp.processed, 100 / 1.125); near(gcp.outputs["cdc-out"], 79.2); near(gcp.pressurePct, 562.5); near(gcp.latencyMs, 6000);
  });
  it("Hot keys and partition counts change diagnostics without adding an unobserved capacity throttle", () => {
    const normal = evaluatePartitioned(base, 500);
    for (const patch of [{ hotKeyShare: 1 }, { partitionCount: 1 }]) {
      const r = evaluatePartitioned({ ...base, ...patch }, 500);
      near(r.hottestPartitionRps, 500); near(r.processed, normal.processed); near(r.capacity, normal.capacity); near(r.conditionalAccepted, normal.conditionalAccepted);
    }
  });
  it("Read mix and replication affect budget, while conflict and consistency affect CDC rather than intake", () => {
    near(partitionedBudget({ ...base, readRatio: 0 }).capacity, 40000 / 1.5);
    near(partitionedBudget({ ...base, readRatio: 1 }).capacity, 40000);
    near(partitionedBudget({ ...base, replicationFactor: 1 }).capacity, 40000);
    for (const [mode, cdc] of [["one", 495], ["quorum", 445.5], ["all", 396]] as const) {
      const r = evaluatePartitioned({ ...base, consistencyMode: mode }, 500);
      near(r.processed, 500); near(r.conditionalAccepted, cdc);
    }
    const conflict = evaluatePartitioned({ ...base, conditionalConflictRate: .25 }, 500);
    near(conflict.conditionalRejected, 125); near(conflict.conditionalAccepted, 337.5); near(conflict.processed, 500);
    near(evaluatePartitioned({ ...base, conditionalConflictRate: 1 }, 500).outputs["cdc-out"], 0);
  });
  it("Zero configured denominators are guarded; allocation and snapshots are non-cumulative diagnostic formulas", () => {
    const c = { ...base, idAllocationMode: "atomic-counter", allocationRangeSize: 0, snapshotIntervalTicks: 0, replicationFactor: 0, serviceLatencyMs: 0 }, r = evaluatePartitioned(c, 500, { tick: 12 });
    near(r.replicationFactor, 1); near(r.allocationCoordinationOps, 500); near(r.allocationCollisions, 0); near(r.snapshotsCreated, 12); near(r.operationLogLength, 488); near(r.replayOperations, 488); near(r.latencyMs, 0);
    const c2 = { ...base, idAllocationMode: "atomic-counter", allocationRangeSize: 100 }, s = evaluatePartitioned(c2, 500, { tick: 20 });
    near(s.allocationCoordinationOps, 5); near(s.snapshotsCreated, 2); near(s.operationLogLength, 498);
    expect(evaluatePartitioned(c2, 500, { tick: 20 })).toEqual(s);
  });
  it("Unavailable paths emit nothing, zero budgets stay finite, explicit Slow scales only own budget/time and no random values are used", () => {
    const failed = evaluatePartitioned(base, 500, { tick: 20, failed: true });
    near(failed.processed, 0); near(failed.conditionalAccepted, 0); near(failed.snapshotsCreated, 0); expect(failed.outputs).toEqual({}); near(failed.rejected, 500);
    const zero = evaluatePartitioned({ ...base, capacityRps: 0 }, 500);
    near(zero.processed, 0); expect(Number.isFinite(zero.latencyMs)).toBe(true); near(zero.outputs["cdc-out"], 0);
    const slow = evaluatePartitioned(base, 500, { capacityFactor: .2 });
    near(slow.capacity, partitionedBudget(base).capacity / 5); near(slow.serviceMs, 25);
  });
  it("Invalid fractions, enums, nonfinite inputs and fractional counters fail rather than producing invented metrics", () => {
    for (const patch of [{ readRatio: 2 }, { hotKeyShare: -1 }, { replicationFactor: .5 }, { partitionCount: 0 }, { serviceLatencyMs: -1 }, { consistencyMode: "eventual" }, { idAllocationMode: "random" }, { snapshotIntervalTicks: .5 }, { allocationRangeSize: NaN }])
      expect(() => evaluatePartitioned({ ...base, ...patch }, 500)).toThrow();
    for (const input of [-1, NaN, Infinity]) expect(() => evaluatePartitioned(base, input)).toThrow();
    expect(() => evaluatePartitioned(base, 500, { tick: .5 })).toThrow();
    expect(() => evaluatePartitioned(base, 500, { capacityFactor: 2 })).toThrow();
  });
});
