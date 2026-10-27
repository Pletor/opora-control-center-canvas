// Převedeno z prototypu `test/cloud-partitioned.test.mjs` (první polovina; zbytek v `cloud-partitioned-2.test.ts`); nic nevynecháno.
import { describe, expect, it } from "vitest";
import { createSimulationNode } from "./model-adapter";
import { connect } from "../../logic/model-rules";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";

const types = ["aws-dynamodb", "gcp-bigtable", "aliyun-tablestore"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);
const nearCard = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(.0051);

function fixture(type = "aws-dynamodb") {
  const d = materializeScenario("cloud-partitioned-" + type);
  return { d, store: d.nodes.find((n) => n.type === type)!, service: d.nodes.find((n) => n.type === "service")!, index: d.nodes.find((n) => n.type === "search-ranking-index")! };
}

describe("cloud-partitioned", () => {
  it("All provider record graphs separate actual admitted500 from CDC445.5 and use their own queue latency", () => {
    for (const type of types) {
      const { d, store, index } = fixture(type), before = structuredClone(d), s = stepSimulation(d), r = s.nodes[store.id];
      near(r.offered, 500);
      near(r.processed, 500);
      near(r.technology.conditionalRejected, 5);
      near(r.technology.conditionalAccepted, 445.5);
      near(s.nodes[index.id].offered, 445.5);
      near(s.nodes[index.id].processed, 445.5);
      near(s.summary!.completed, 500);
      expect(r.technology.durableLogVerified).toBe(false);
      expect(d).toEqual(before);
      expect(stepSimulation(d)).toEqual(s);
      expect(d.edges.length).toBe(4);
    }
  });

  it("Source capacity100 limits actual input edges while read/replication cost and CDC remain separate budgets", () => {
    for (const [type, cap, cdc, pressure, latency] of [["aws-dynamodb", 100 / 1.1, 81, 550, 5000], ["gcp-bigtable", 100 / 1.125, 79.2, 562.5, 6000]] as const) {
      const { d, store, index } = fixture(type);
      store.config.model = { capacityRps: 100 };
      const s = stepSimulation(d), edge = d.edges.find((e) => e.to.nodeId === store.id)!, r = s.nodes[store.id];
      near(r.processed, cap);
      near(r.pressurePct, pressure);
      near(r.latencyMs, latency);
      near(s.nodes[index.id].offered, cdc);
      nearCard(s.edges[edge.id].accepted, cap);
      nearCard(s.edges[edge.id].rejected, 500 - cap);
    }
  });

  it("Real inspector-equivalent config edits change CDC/diagnostics with no phantom hot-key admission losses or history advancement", () => {
    const { d, store, index } = fixture();
    let s = stepSimulation(d);
    for (const [patch, cdc, hot] of [[{ hotKeyShare: 1 }, 445.5, 500], [{ partitionCount: 1 }, 445.5, 500], [{ conditionalConflictRate: .25 }, 337.5, 78.125], [{ consistencyMode: "one" }, 495, 78.125], [{ consistencyMode: "all" }, 396, 78.125]] as const) {
      store.config.model = patch;
      const before = structuredClone(s), p = previewSimulation(d, s);
      near(p.nodes[store.id].processed, 500);
      near(p.nodes[store.id].technology.hottestPartitionRps, hot);
      near(p.nodes[index.id].offered, cdc);
      expect(p.tick).toBe(s.tick);
      expect(p.samples).toEqual(s.samples);
      expect(s).toEqual(before);
      s = stepSimulation(d, s);
    }
  });

  it("Telemetry defaults to processed1x, both output overrides change actual peer input and unavailable components override nothing", () => {
    const { d, store, index } = fixture(), monitor = createSimulationNode("monitoring");
    d.nodes.push(monitor);
    d.edges.push(connect(d, { nodeId: store.id, portId: "telemetry-out" }, { nodeId: monitor.id, portId: "telemetry-in" }).edge);
    let s = stepSimulation(d);
    near(s.nodes[monitor.id].offered, 500);
    store.config.outputOverrides = { "cdc-out": 27.5, "telemetry-out": 37.5 };
    const p = previewSimulation(d, s);
    near(p.nodes[index.id].offered, 27.5);
    near(p.nodes[monitor.id].offered, 37.5);
    near(p.nodes[store.id].processed, 500);
    modelCommand(s, d, "crash", [store.id]);
    s = stepSimulation(d, s);
    near(s.nodes[index.id].offered, 0);
    near(s.nodes[monitor.id].offered, 0);
    near(s.nodes[store.id].processed, 0);
  });

  it("Failure/recovery and combined sustained pressure are deterministic without consuming an extra resilience tick in preview", () => {
    const { d, store, index } = fixture();
    store.config.model = { capacityRps: 100, crashAfterTicks: 2 };
    let s = stepSimulation(d);
    expect(s.nodes[store.id].overloadTicks).toBe(1);
    const before = structuredClone(s), p = previewSimulation(d, s);
    expect(s).toEqual(before);
    expect(p.nodes[store.id].overloadTicks).toBe(1);
    s = stepSimulation(d, s);
    expect(s.nodes[store.id].autoFailed).toBe(true);
    near(s.nodes[index.id].offered, 0);
    store.config.model = {};
    for (let i = 0; i < 2; i++) s = stepSimulation(d, s);
    expect(s.nodes[store.id].autoFailed).toBe(false);
    near(s.nodes[index.id].offered, 445.5);
    modelCommand(s, d, "crash", [store.id]);
    s = stepSimulation(d, s);
    modelCommand(s, d, "restore", [store.id]);
    const q = previewSimulation(d, s);
    near(q.nodes[store.id].processed, 0);
    expect(q.nodes[store.id].state).toBe("recovering");
    for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
    near(s.nodes[store.id].processed, 500);
    near(s.nodes[index.id].offered, 445.5);
    expect(s.events.some((e) => e.kind === "recovery")).toBe(true);
  });
});
