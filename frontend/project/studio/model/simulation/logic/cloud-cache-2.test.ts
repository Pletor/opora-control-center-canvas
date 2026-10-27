// Převedeno z prototypu `test/cloud-cache.test.mjs` (druhá polovina; začátek v `cloud-cache.test.ts`); vynecháno:
// `exportProject`/`importProject` projektu (nahrazeno JSON round-tripem modelu přes `validateSimulationModel`).
import { describe, expect, it } from "vitest";
import { connect, connectionError } from "../../logic/model-rules";
import { emptyStudioModel } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";

type Cfg = Record<string, any>;
const types = ["aws-elasticache", "gcp-memorystore", "aliyun-tair"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

function fixture(type: string) {
  const d = materializeScenario("cloud-cache-" + type);
  return { d, cache: d.nodes.find((n) => n.type === type)!, db: d.nodes.find((n) => n.type === "postgresql")!, service: d.nodes.find((n) => n.type === "service")! };
}

describe("cloud-cache (2)", () => {
  it("Serverless handlers and services share the same managed-cache prediction rather than generic Redis defaults", () => {
    for (const [cacheType, hit] of types.map((t, i) => [t, [.85, .84, .88][i]] as const)) {
      const d = materializeScenario("cloud-serverless-aws-lambda"), f = d.nodes.find((n) => n.type === "aws-lambda")!, db = d.nodes.find((n) => n.type === "postgresql")!, cache = createSimulationNode(cacheType);
      d.nodes.push(cache);
      d.edges.push(connect(d, { nodeId: f.id, portId: "cache-out" }, { nodeId: cache.id, portId: "cache-in" }).edge);
      let s = stepSimulation(d);
      near(s.nodes[f.id].technology.cacheHits, 250 * hit);
      near(s.nodes[cache.id].technology.hits, 250 * hit);
      near(s.nodes[db.id].offered, 250 * (1 - hit));
      f.config.outputOverrides = { "cache-out": 0 };
      s = stepSimulation(d);
      near(s.nodes[cache.id].processed, 0);
      near(s.nodes[db.id].offered, 250);
    }
  });

  it("Multiple cache targets divide checks and combine their admitted hit volumes; disabled edges carry no checks", () => {
    const { d, cache, db, service } = fixture("aws-elasticache"), other = createSimulationNode("gcp-memorystore");
    cache.config.model = { capacityRps: 50 };
    d.nodes.push(other);
    const second = connect(d, { nodeId: service.id, portId: "cache-out" }, { nodeId: other.id, portId: "cache-in" }).edge;
    d.edges.push(second);
    let s = stepSimulation(d);
    near(s.nodes[cache.id].offered, 125);
    near(s.nodes[other.id].offered, 125);
    near(s.nodes[db.id].offered, 250 - 50 * .85 - 125 * .84);
    second.enabled = false;
    s = stepSimulation(d);
    near(s.nodes[cache.id].offered, 250);
    near(s.nodes[other.id].offered, 0);
    near(s.nodes[db.id].offered, 207.5);
  });

  it("Typed ports, source-bound configurations and persisted definitions retain identity without cache runtime state", () => {
    for (const type of types) {
      const { d, cache, service } = fixture(type);
      cache.config.model = { cacheHitRate: .4, ttlSeconds: 30, memoryLimitMb: 512, evictionPolicy: "ttl", partitionCount: 3 };
      (cache.config.model as Cfg).workingSetMb = 0;
      const raw = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(raw))).toEqual(d);
      expect(raw.includes("effectiveHitRate")).toBe(false);
      expect(raw.includes("clusterLifecycleModeled")).toBe(false);
      expect(connectionError(d, { nodeId: service.id, portId: "sql-out" }, { nodeId: cache.id, portId: "cache-in" })).toBeTruthy();
      for (const patch of [{ cacheHitRate: 2 }, { partitionCount: 1.5 }, { evictionPolicy: "random" }, { workingSetMb: -1 }, { memoryLimitMb: -1 }, { crashThresholdPct: 401 }]) {
        cache.config.model = patch;
        expect(() => validateSimulationModel(d)).toThrow();
      }
    }
  });

  it("Adding zero-working-set cache support preserves the previous positive AI working-set contract", () => {
    const p = emptyStudioModel("model-ai"), ai = createSimulationNode("ai-inference");
    p.nodes.push(ai);
    ai.config.model = { workingSetMb: 0 };
    expect(() => validateSimulationModel(p)).toThrow();
    (ai.config.model as Cfg).workingSetMb = 1;
    validateSimulationModel(p);
  });
});
