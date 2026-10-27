// Převedeno z prototypu `test/serverless-model.test.mjs`; vynecháno: nic.
import { describe, expect, it } from "vitest";
import { executeServerless, serverlessBudget } from "./serverless-model";

const defaults = { reservedConcurrency: 1, instanceConcurrency: 1, coldStartLatencyMs: 180, coldStartShare: 0, memoryMb: 1024, serviceLatencyMs: 100, telemetryRate: .02 };

describe("serverless-model", () => {
  it("Explicit one-second fluid budget conserves fractional offered work at and beyond the ceiling", () => {
    for (const offered of [0, .5, 10, 10.25, 250]) {
      const r = executeServerless(defaults, offered);
      expect(r.capacity).toBe(10); expect(r.processed).toBe(Math.min(offered, 10)); expect(r.offered).toBe(r.processed + r.rejected);
      expect(r.rejected).toBe(r.throttled); expect(r.unavailable).toBe(0); expect(r.activeInstances).toBe(1);
    }
  });
  it("Configured cold fraction affects weighted duration and budget, not random admission", () => {
    const c = { ...defaults, coldStartShare: .5, coldStartLatencyMs: 100 }, r = executeServerless(c, 5);
    expect(r.meanDurationMs).toBe(150); expect(r.capacity).toBe(1000 / 150); expect(r.coldInvocations).toBe(2.5); expect(r.warmInvocations).toBe(2.5); expect(r.latencyMs).toBe(150); expect(r.telemetry).toBe(.1);
  });
  it("Memory, invocation concurrency, reserved instances and logical replicas remain separate quantities", () => {
    const r = executeServerless({ ...defaults, memoryMb: 2048, instanceConcurrency: 4, reservedConcurrency: 2 }, 200, { replicas: 3 });
    expect(r.capacity).toBe(480); expect(r.instanceBudget).toBe(80); expect(r.maximumInstances).toBe(6); expect(r.activeInstances).toBe(3); expect(r.cpuShare).toBe(2); expect(r.processed).toBe(200); expect(r.pressurePct).toBe(200 / 480 * 100);
  });
  it("Failure rejects all work without claiming throttling; restore cannot complete lost prior invocations", () => {
    const outage = executeServerless(defaults, 250, { failed: true });
    expect(outage.completed).toBe(0); expect(outage.unavailable).toBe(250); expect(outage.throttled).toBe(0); expect(outage.activeInstances).toBe(0); expect(outage.coldInvocations).toBe(0); expect(outage.telemetry).toBe(0);
    const restored = executeServerless(defaults, 2);
    expect(restored.completed).toBe(2); expect(restored.rejected).toBe(0);
  });
  it("Slow capacity factor reduces admission and reports the corresponding deterministic processing slowdown", () => {
    const r = executeServerless(defaults, 10, { capacityFactor: .5 });
    expect(r.capacity).toBe(5); expect(r.completed).toBe(5); expect(r.throttled).toBe(5); expect(r.latencyMs).toBe(200); expect(r.activeInstances).toBe(1);
  });
  it("Repeated identical inputs are deterministic and do not mutate definitions", () => {
    const c = structuredClone(defaults), before = structuredClone(c), r = executeServerless(c, 13.3);
    for (let n = 0; n < 100; n++) expect(executeServerless(c, 13.3)).toEqual(r);
    expect(c).toEqual(before); expect(Object.values(r).every((v) => typeof v !== "number" || Number.isFinite(v))).toBe(true);
  });
  it("Invalid definitions and runtime inputs fail before returning invented metrics", () => {
    for (const patch of [{ reservedConcurrency: 0 }, { instanceConcurrency: 1.2 }, { memoryMb: NaN }, { coldStartShare: 2 }, { serviceLatencyMs: 0 }]) expect(() => serverlessBudget({ ...defaults, ...patch })).toThrow(RangeError);
    for (const offered of [-1, Infinity, NaN]) expect(() => executeServerless(defaults, offered)).toThrow(RangeError);
    for (const options of [{ replicas: 0 }, { replicas: 1.5 }, { capacityFactor: -1 }, { capacityFactor: Infinity }]) expect(() => executeServerless(defaults, 1, options)).toThrow(RangeError);
  });
});
