// Převedeno z prototypu `test/cloud-partitioned.test.mjs` (druhá polovina; začátek v `cloud-partitioned.test.ts`); vynecháno:
// `exportProject`/`importProject` projektu (nahrazeno JSON round-tripem modelu přes `validateSimulationModel`).
import { describe, expect, it } from "vitest";
import { connect, connectionError } from "../../logic/model-rules";
import { emptyStudioModel } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { previewSimulation, stepSimulation } from "./simulation";
import { validateModelConfig } from "./simulation-config";
import type { SimulationState } from "./simulation-types";
import { validateSimulationModel } from "./simulation-validate";

const types = ["aws-dynamodb", "gcp-bigtable", "aliyun-tablestore"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);
const nearCard = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(.0051);

function fixture(type = "aws-dynamodb") {
  const d = materializeScenario("cloud-partitioned-" + type);
  return { d, store: d.nodes.find((n) => n.type === type)!, service: d.nodes.find((n) => n.type === "service")!, index: d.nodes.find((n) => n.type === "search-ranking-index")! };
}

describe("cloud-partitioned (2)", () => {
  it("Zero service time and guarded denominators are new-profile scoped; allocations/logs are diagnostics at committed project time", () => {
    const { d, store } = fixture();
    store.config.model = { serviceLatencyMs: 0, replicationFactor: 0, allocationRangeSize: 0, snapshotIntervalTicks: 0, idAllocationMode: "atomic-counter" };
    let s: SimulationState | undefined;
    for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
    near(s!.nodes[store.id].latencyMs, 0);
    near(s!.nodes[store.id].technology.allocationCoordinationOps, 500);
    near(s!.nodes[store.id].technology.snapshotsCreated, 4);
    near(s!.nodes[store.id].technology.operationLogLength, 496);
    near(previewSimulation(d, s!).nodes[store.id].technology.snapshotsCreated, 4);
    expect(() => validateModelConfig({ serviceLatencyMs: 0 }, "aws-lambda")).toThrow();
    expect(() => validateModelConfig({ serviceLatencyMs: 0 }, "ai-inference")).toThrow();
    validateModelConfig({ serviceLatencyMs: 0 }, "aws-dynamodb");
  });

  it("Persisted enum/zero definitions roundtrip without runtime and invalid typed/semantic settings are rejected", () => {
    for (const type of types) {
      const { d, store, service } = fixture(type);
      store.config.model = { serviceLatencyMs: 0, replicationFactor: 0, allocationRangeSize: 0, snapshotIntervalTicks: 0, idAllocationMode: "atomic-counter", consistencyMode: "all" };
      validateSimulationModel(d);
      const raw = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(raw))).toEqual(d);
      expect(raw.includes("durableLogVerified")).toBe(false);
      expect(connectionError(d, { nodeId: service.id, portId: "sql-out" }, { nodeId: store.id, portId: "record-in" })).toBeTruthy();
      for (const patch of [{ consistencyMode: "eventual" }, { idAllocationMode: "random" }, { partitionCount: 0 }, { conditionalConflictRate: 2 }, { allocationRangeSize: .5 }, { crashThresholdPct: 401 }]) {
        store.config.model = patch;
        expect(() => validateSimulationModel(d)).toThrow();
      }
    }
  });

  it("Two record writers share admitted volume while exactly one CDC budget reaches the consumer", () => {
    const { d, store, index } = fixture(), lb = d.nodes.find((n) => n.type === "load-balancer")!, other = createSimulationNode("service");
    d.nodes.push(other);
    d.edges.push(connect(d, { nodeId: lb.id, portId: "http-out" }, { nodeId: other.id, portId: "http-in" }).edge);
    d.edges.push(connect(d, { nodeId: other.id, portId: "record-out" }, { nodeId: store.id, portId: "record-in" }).edge);
    store.config.model = { capacityRps: 100 };
    const s = stepSimulation(d), edges = d.edges.filter((e) => e.to.nodeId === store.id);
    near(s.nodes[store.id].processed, 100 / 1.1);
    near(s.nodes[index.id].offered, 81);
    for (const e of edges) nearCard(s.edges[e.id].accepted, 50 / 1.1);
    // Two independently rounded45.45 edge displays sum90.9; the node retains90.909….
    near(edges.reduce((n, e) => n + s.edges[e.id].accepted, 0), 90.9);
  });

  it("An explicit Producer/Queue/Worker record path operates for all three provider stores", () => {
    for (const type of types) {
      const d = emptyStudioModel("model-record-path"), producer = createSimulationNode("event-producer"), queue = createSimulationNode("queue"), worker = createSimulationNode("worker"), store = createSimulationNode(type), index = createSimulationNode("search-ranking-index");
      producer.config.model = { rate: 500 };
      d.nodes.push(producer, queue, worker, store, index);
      for (const [a, out, b, input] of [[producer, "event-out", queue, "event-in"], [queue, "job-out", worker, "job-in"], [worker, "record-out", store, "record-in"], [store, "cdc-out", index, "index-in"]] as const)
        d.edges.push(connect(d, { nodeId: a.id, portId: out }, { nodeId: b.id, portId: input }).edge);
      validateSimulationModel(d);
      const s = stepSimulation(d);
      near(s.nodes[worker.id].processed, 500);
      near(s.nodes[store.id].processed, 500);
      near(s.nodes[index.id].offered, 445.5);
    }
  });
});
