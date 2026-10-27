// Převedeno z prototypu `test/cloud-object.test.mjs` (první polovina; zbytek v `cloud-object-2.test.ts`); nic nevynecháno.
import { describe, expect, it } from "vitest";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import { config } from "./simulation-config";

type Cfg = Record<string, any>;
const types = ["aws-s3", "gcp-gcs", "aliyun-oss"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

function fixture(type = "aws-s3") {
  const d = materializeScenario("cloud-object-" + type);
  return { d, store: d.nodes.find((n) => n.type === type)!, worker: d.nodes.find((n) => n.type === "worker")!, f: d.nodes.find((n) => n.type === "aws-lambda")! };
}

describe("cloud-object", () => {
  it("Three explicit producer/queue/worker/object/function paths carry actual offered events with observed provider budgets and node latency", () => {
    for (const [index, type] of types.entries()) {
      const { d, store, f } = fixture(type), before = structuredClone(d), s = stepSimulation(d), r = s.nodes[store.id], m = r.technology;
      expect(d.edges.length).toBe(4);
      near(r.offered, 500);
      near(r.processed, 500);
      near(r.capacity, [25000, 24000, 22500][index]);
      near(m.egressMbps, 1000);
      near(s.nodes[f.id].offered, 500);
      near(s.nodes[f.id].processed, 500);
      expect(Math.round(r.latencyMs * 10) / 10).toBe([35.7, 40.9, 38.9][index]);
      expect(m.persistenceVerified).toBe(false);
      expect(m.diagnosticPoliciesOnly).toBe(true);
      expect(d).toEqual(before);
      expect(stepSimulation(d)).toEqual(s);
    }
  });

  it("Source request100, bandwidth100 and object100MB controls bound actual data edges, events and distinct latency fields", () => {
    const { d, store, f } = fixture();
    for (const [patch, served, egress, ttfb] of [[{ requestCapacityRps: 100 }, 100, 200, 175], [{ egressBandwidthMbps: 100 }, 50, 100, 350], [{ objectSizeMb: 100 }, 62.5, 50000, 280]] as const) {
      store.config.model = patch;
      const s = stepSimulation(d), m = s.nodes[store.id].technology, edge = d.edges.find((e) => e.to.nodeId === store.id)!;
      near(m.processed, served);
      near(m.egressMbps, egress);
      near(m.firstByteEstimateMs, ttfb);
      near(m.latencyMs, 35000);
      near(s.edges[edge.id].accepted, served);
      near(s.edges[edge.id].rejected, 500 - served);
      near(s.nodes[f.id].offered, served);
      near(s.nodes[f.id].processed, served);
    }
  });

  it("Access, aggregate verification and retries remain diagnostic rather than fictitious admission or persistence gates", () => {
    const { d, store, f } = fixture();
    store.config.model = { accessMode: "private", aclRejectRate: .2, verificationFailureRate: .5, failedPartRetryLimit: 0 };
    const s = stepSimulation(d), m = s.nodes[store.id].technology;
    near(m.accessRejected, 150);
    near(m.accessAccepted, 350);
    near(m.parts, 16);
    near(m.verificationFailures, 8);
    near(m.verifiedParts, 8);
    near(m.retriedParts, 0);
    near(m.processed, 500);
    near(s.nodes[f.id].processed, 500);
    (store.config.model as Cfg).failedPartRetryLimit = 3;
    const next = previewSimulation(d, s);
    near(next.nodes[store.id].technology.retriedParts, 8);
    near(next.nodes[store.id].technology.verifiedParts, 8);
    near(next.nodes[f.id].processed, 500);
  });

  it("Manual Crash/Restore preview and next Step, sustained overload, automatic recovery and Slow are explicit repeatable transitions", () => {
    for (const type of types) {
      const { d, store, f } = fixture(type);
      let s = stepSimulation(d);
      modelCommand(s, d, "crash", [store.id]);
      s = stepSimulation(d, s);
      near(s.nodes[store.id].processed, 0);
      near(s.nodes[f.id].offered, 0);
      modelCommand(s, d, "restore", [store.id]);
      const old = structuredClone(s), p = previewSimulation(d, s);
      expect(s).toEqual(old);
      expect(p.nodes[store.id].state).toBe("recovering");
      near(p.nodes[f.id].offered, 0);
      s = stepSimulation(d, s);
      near(s.nodes[store.id].processed, 500);
      near(s.nodes[f.id].offered, 500);
      expect(s.events.some((e) => e.kind === "recovery")).toBe(true);
      store.config.model = { requestCapacityRps: 100, crashThresholdPct: 400, crashAfterTicks: 2 };
      s = stepSimulation(d);
      expect(s.nodes[store.id].overloadTicks).toBe(1);
      const before = structuredClone(s), p2 = previewSimulation(d, s);
      expect(p2.tick).toBe(s.tick);
      expect(s).toEqual(before);
      expect(p2.nodes[store.id].overloadTicks).toBe(1);
      s = stepSimulation(d, s);
      expect(s.nodes[store.id].autoFailed).toBe(true);
      near(s.nodes[f.id].offered, 0);
      store.config.model = {};
      for (let i = 0; i < 2; i++) s = stepSimulation(d, s);
      expect(s.nodes[store.id].autoFailed).toBe(false);
      near(s.nodes[f.id].offered, 500);
      modelCommand(s, d, "slow", [store.id]);
      s = stepSimulation(d, s);
      near(s.nodes[store.id].capacity, config(store).capacity / 5);
      expect(s.nodes[store.id].slow).toBe(true);
    }
  });
});
