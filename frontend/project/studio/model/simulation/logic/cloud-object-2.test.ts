// Převedeno z prototypu `test/cloud-object.test.mjs` (druhá polovina; začátek v `cloud-object.test.ts`); vynecháno:
// `exportProject`/`importProject` projektu (nahrazeno JSON round-tripem modelu přes `validateSimulationModel`).
import { describe, expect, it } from "vitest";
import { connect, connectionError } from "../../logic/model-rules";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { modelCommand, stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";

const types = ["aws-s3", "gcp-gcs", "aliyun-oss"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

function fixture(type = "aws-s3") {
  const d = materializeScenario("cloud-object-" + type);
  return { d, store: d.nodes.find((n) => n.type === type)!, worker: d.nodes.find((n) => n.type === "worker")!, f: d.nodes.find((n) => n.type === "aws-lambda")! };
}

describe("cloud-object (2)", () => {
  it("Failed consumers and explicit event overrides separate generated offers from delivered function work", () => {
    const { d, store, f } = fixture();
    let s = stepSimulation(d);
    modelCommand(s, d, "crash", [f.id]);
    s = stepSimulation(d, s);
    near(s.nodes[store.id].processed, 500);
    near(s.nodes[f.id].processed, 0);
    const edge = d.edges.find((e) => e.from.nodeId === store.id)!;
    near(s.edges[edge.id].offered, 500);
    near(s.edges[edge.id].accepted, 0);
    delete s.incidents[f.id];
    store.config.outputOverrides = { "event-out": 27.5 };
    s = stepSimulation(d, s);
    near(s.nodes[store.id].processed, 500);
    near(s.nodes[f.id].offered, 27.5);
    (store.config.outputOverrides as Record<string, number>)["event-out"] = 0;
    s = stepSimulation(d, s);
    near(s.nodes[f.id].offered, 0);
    (store.config.outputOverrides as Record<string, number>)["event-out"] = 100;
    modelCommand(s, d, "crash", [store.id]);
    s = stepSimulation(d, s);
    near(s.nodes[f.id].offered, 0);
  });

  it("Multiple writers share the actual object request budget proportionally without inventing extra objects", () => {
    const { d, store, worker } = fixture(), other = createSimulationNode("worker");
    d.nodes.push(other);
    const queue = d.nodes.find((n) => n.type === "queue")!;
    d.edges.push(connect(d, { nodeId: queue.id, portId: "job-out" }, { nodeId: other.id, portId: "job-in" }).edge);
    d.edges.push(connect(d, { nodeId: other.id, portId: "data-out" }, { nodeId: store.id, portId: "data-in" }).edge);
    store.config.model = { requestCapacityRps: 100 };
    const s = stepSimulation(d), data = d.edges.filter((e) => e.to.nodeId === store.id);
    near(s.nodes[worker.id].processed, 250);
    near(s.nodes[other.id].processed, 250);
    near(s.nodes[store.id].processed, 100);
    near(data.reduce((n, e) => n + s.edges[e.id].accepted, 0), 100);
    for (const e of data) near(s.edges[e.id].accepted, 50);
  });

  it("Observed object event roles reject generic queues/workflows; schema definitions roundtrip enum/zero settings without volatile receipts", () => {
    for (const type of types) {
      const { d, store, worker } = fixture(type), queue = createSimulationNode("queue"), workflow = createSimulationNode("workflow-orchestrator");
      d.nodes.push(queue, workflow);
      expect(connectionError(d, { nodeId: store.id, portId: "event-out" }, { nodeId: queue.id, portId: "event-in" })).toBeTruthy();
      expect(connectionError(d, { nodeId: store.id, portId: "event-out" }, { nodeId: workflow.id, portId: "event-in" })).toBeTruthy();
      expect(connectionError(d, { nodeId: worker.id, portId: "sql-out" }, { nodeId: store.id, portId: "data-in" })).toBeTruthy();
      store.config.model = { accessMode: "private", multipartPartSizeMb: 0, stressThresholdPct: 0, failedPartRetryLimit: 0 };
      store.config.outputOverrides = { "event-out": 0 };
      validateSimulationModel(d);
      const raw = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(raw))).toEqual(d);
      expect(raw.includes("persistenceVerified")).toBe(false);
      for (const patch of [{ objectSizeMb: 0 }, { requestCapacityRps: -1 }, { aclRejectRate: 2 }, { accessMode: "authenticated" }, { failedPartRetryLimit: .5 }, { crashThresholdPct: 401 }]) {
        store.config.model = patch;
        expect(() => validateSimulationModel(d)).toThrow();
      }
    }
  });
});
