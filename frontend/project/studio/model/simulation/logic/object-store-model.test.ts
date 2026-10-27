// Převedeno z prototypu `test/object-store-model.test.mjs`; vynecháno: nic. Pozorování (profile `object-store`) jsou konstanty
// z `analysis/evidence/extended-catalog-observations.json` (items[].defaults pro aws-s3, gcp-gcs, aliyun-oss).
import { describe, expect, it } from "vitest";
import { evaluateObjectStore, objectStoreBudget } from "./object-store-model";

const common = { objectSizeMb: .25, accessMode: "signed", multipartPartSizeMb: 8, verificationFailureRate: 0, aclRejectRate: 0, failedPartRetryLimit: 3, stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2 };
const items: { id: string; defaults: Record<string, any> }[] = [
  { id: "aws-s3", defaults: { ...common, requestCapacityRps: 35000, egressBandwidthMbps: 50000, firstByteLatencyMs: 35 } },
  { id: "gcp-gcs", defaults: { ...common, requestCapacityRps: 30000, egressBandwidthMbps: 48000, firstByteLatencyMs: 40 } },
  { id: "aliyun-oss", defaults: { ...common, requestCapacityRps: 32000, egressBandwidthMbps: 45000, firstByteLatencyMs: 38 } },
];
const base = items[0].defaults;
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

describe("object-store-model", () => {
  it("All provider baseline budgets admit500model operations and expose aggregate parts without claiming persisted objects", () => {
    for (const item of items) {
      const r = evaluateObjectStore(item.defaults, 500);
      near(r.processed, 500); near(r.rejected, 0); near(r.egressMbps, 1000); near(r.parts, 16); near(r.outputs["event-out"], 500);
      expect(r.diagnosticPoliciesOnly).toBe(true); expect(r.persistenceVerified).toBe(false);
      near(r.latencyMs, item.defaults.firstByteLatencyMs / (1 - 500 / r.capacity)); expect(r.limiter).toBe("egress-bandwidth");
    }
  });
  it("Independent request, bandwidth and object-size source cases expose the actual limiting budget", () => {
    const request = evaluateObjectStore({ ...base, requestCapacityRps: 100 }, 500);
    near(request.processed, 100); near(request.rejected, 400); expect(request.limiter).toBe("request-ceiling"); near(request.latencyMs, 35000); near(request.firstByteEstimateMs, 175);
    const bandwidth = evaluateObjectStore({ ...base, egressBandwidthMbps: 100 }, 500);
    near(bandwidth.processed, 50); near(bandwidth.rejected, 450); near(bandwidth.egressMbps, 100); near(bandwidth.latencyMs, 35000); near(bandwidth.firstByteEstimateMs, 350);
    const size = evaluateObjectStore({ ...base, objectSizeMb: 100 }, 500);
    near(size.capacity, 62.5); near(size.processed, 62.5); near(size.rejected, 437.5); near(size.parts, 782); near(size.firstByteEstimateMs, 280);
  });
  it("Observed private ACL and verification fields change diagnostics without silently enforcing access or suppressing events", () => {
    const r = evaluateObjectStore({ ...base, accessMode: "private", aclRejectRate: .2, verificationFailureRate: .5, failedPartRetryLimit: 0 }, 500);
    near(r.accessRejected, 150); near(r.accessAccepted, 350); near(r.parts, 16); near(r.verificationFailures, 8); near(r.verifiedParts, 8); near(r.retriedParts, 0);
    near(r.processed, 500); near(r.outputs["event-out"], 500); expect(r.persistenceVerified).toBe(false);
  });
  it("Retries account for retransmitted model MB but do not retroactively turn failed verification into a persistence receipt", () => {
    for (const failedPartRetryLimit of [0, 1, 3]) {
      const r = evaluateObjectStore({ ...base, verificationFailureRate: .5, failedPartRetryLimit }, 500);
      near(r.retriedParts, failedPartRetryLimit ? 8 : 0); near(r.retransmittedBytesMb, failedPartRetryLimit ? 64 : 0); near(r.verifiedParts, 8); near(r.processed, 500);
    }
    const overlap = evaluateObjectStore({ ...base, aclRejectRate: 1, accessMode: "private" }, 500);
    near(overlap.accessRejected, 550); near(overlap.accessAccepted, 0); near(overlap.rejected, 0); near(overlap.outputs["event-out"], 500);
  });
  it("Aggregate part-size zero guard and zero budgets stay finite and conserve accepted plus rejected operations", () => {
    for (const multipartPartSizeMb of [0, .01, 8]) for (const requestCapacityRps of [0, 100, 35000]) for (const egressBandwidthMbps of [0, 100, 50000]) for (const offered of [0, .5, 500]) {
      const r = evaluateObjectStore({ ...base, multipartPartSizeMb, requestCapacityRps, egressBandwidthMbps }, offered);
      near(r.processed + r.rejected, offered); expect(Number.isSafeInteger(r.parts)).toBe(true);
      expect(Object.values(r).every((v) => typeof v !== "number" || Number.isFinite(v))).toBe(true);
      if (requestCapacityRps === 0 || egressBandwidthMbps === 0) { near(r.processed, 0); near(r.parts, 0); near(r.pressurePct, offered ? 1000 : 0); }
    }
  });
  it("Own Slow and explicit Crash flag preserve capacity conservation and never emit unavailable object notifications", () => {
    const c = { ...base, requestCapacityRps: 100 }, slow = evaluateObjectStore(c, 500, { capacityFactor: .2 }), failed = evaluateObjectStore(c, 500, { failed: true });
    near(slow.processed, 20); near(slow.rejected, 480); near(failed.processed, 0); near(failed.parts, 0); near(failed.accessRejected, 0); near(failed.unavailable, 500);
    expect(failed.outputs).toEqual({}); near(evaluateObjectStore(c, 500).processed, 100);
  });
  it("Request/bandwidth ties are deterministic, repeated evaluations are pure and outputs do not carry durable state", () => {
    const c = { ...base, requestCapacityRps: 500, egressBandwidthMbps: 1000 }, before = structuredClone(c), r = evaluateObjectStore(c, 500);
    expect(r.limiter).toBe("request-ceiling");
    for (let i = 0; i < 50; i++) expect(evaluateObjectStore(c, 500)).toEqual(r);
    expect(c).toEqual(before); expect(objectStoreBudget(c).capacity).toBe(500);
  });
  it("Invalid model bounds and enum values are rejected instead of becoming apparent measured results", () => {
    for (const patch of [{ objectSizeMb: 0 }, { requestCapacityRps: -1 }, { egressBandwidthMbps: Infinity }, { firstByteLatencyMs: 0 }, { accessMode: "authenticated" }, { verificationFailureRate: 2 }, { failedPartRetryLimit: 1.5 }, { multipartPartSizeMb: -1 }])
      expect(() => evaluateObjectStore({ ...base, ...patch }, 500)).toThrow(RangeError);
    for (const offered of [-1, NaN, Infinity]) expect(() => evaluateObjectStore(base, offered)).toThrow(RangeError);
    for (const capacityFactor of [-1, NaN, 2]) expect(() => evaluateObjectStore(base, 1, { capacityFactor })).toThrow(RangeError);
  });
});
