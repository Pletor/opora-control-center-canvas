// Převedeno z prototypu `test/monitoring-model.test.mjs`; vynecháno: nic.
import { describe, expect, it } from "vitest";
import { monitorTelemetry } from "./monitoring-model";

const defaults = { sampleRate: .5, cardinalityLimit: 1000, activeSeries: 100, retentionMinutes: 1, evaluationWindowTicks: 3, alertThresholdPct: 85 };

describe("monitoring-model", () => {
  it("Sampling is intentional filtering, cardinality and ingest loss remain separate, replicas are supplied as aggregate capacity", () => {
    let r = monitorTelemetry(defaults, 250, 1000, 1);
    expect(r.sampled).toBe(125); expect(r.sampledOut).toBe(125); expect(r.processed).toBe(125); expect(r.admitted).toBe(250); expect(r.rejected).toBe(0); expect(r.retained).toBe(125);
    r = monitorTelemetry({ ...defaults, cardinalityLimit: 50 }, 250, 40, 1);
    expect(r.cardinalityDropped).toBe(62.5); expect(r.capacityDropped).toBe(22.5); expect(r.processed).toBe(40); expect(r.admitted).toBe(165); expect(r.rejected).toBe(85);
  });
  it("Alert needs the configured consecutive window and clears on actual lower pressure; preview replays current basis", () => {
    let old: any;
    for (let tick = 1; tick <= 3; tick++) {
      old = monitorTelemetry(defaults, 250, 100, tick, old);
      expect(old.alert).toBe(tick === 3);
      const before = structuredClone(old), p = monitorTelemetry(defaults, 250, 100, tick, old, true);
      expect(old).toEqual(before); expect(p.alertTicks).toBe(tick); expect(p.retained).toBe(old.retained);
    }
    expect(old.health).toBe(0);
    const healthy = monitorTelemetry(defaults, 20, 100, 4, old);
    expect(healthy.alertTicks).toBe(0); expect(healthy.health).toBe(1);
  });
  it("Retention expires at model-time boundary even during outage; recovery does not manufacture lost samples", () => {
    const c = { ...defaults, retentionMinutes: 1 / 60 };
    let old: any = monitorTelemetry(c, 250, 1000, 1);
    expect(old.retained).toBe(125);
    old = monitorTelemetry(c, 250, 1000, 2, old, false, true);
    expect(old.retained).toBe(0); expect(old.expired).toBe(125); expect(old.health).toBe(0); expect(old.admitted).toBe(0);
    old = monitorTelemetry(c, 250, 1000, 3, old);
    expect(old.retained).toBe(125); expect(old.expired).toBe(0);
  });
});
