// Převedeno z prototypu `test/cache-shared-budget.test.mjs`; vynecháno: nic. `connect` prototypu mutoval doménu; tady pomocník
// `link` volá S4 `connect` s politikou scénáře a vazbu přidá do `model.edges` na místě.
import { describe, expect, it } from "vitest";
import { connect } from "../../logic/model-rules";
import { createSimulationNode } from "./model-adapter";
import { planCacheSettlement } from "./cache-settlement";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";

const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);
const model = (node: { config: Record<string, unknown> }) => node.config.model as Record<string, any>;
type D = ReturnType<typeof materializeScenario>;
function link(d: D, from: { nodeId: string; portId: string }, to: { nodeId: string; portId: string }) {
  const { edge } = connect(d, from, to, d.modelDefinition.connectionPolicy as any, `edge-${d.edges.length + 1}`);
  d.edges.push(edge);
  return edge;
}

function fixture(secondType = "service") {
  const d = materializeScenario("cloud-cache-aws-elasticache"), cache = d.nodes.find((n) => n.type === "aws-elasticache")!, db = d.nodes.find((n) => n.type === "postgresql")!;
  const first = d.nodes.find((n) => n.type === "service")!, lb = d.nodes.find((n) => n.type === "load-balancer")!, second = createSimulationNode(secondType);
  d.nodes.push(second);
  link(d, { nodeId: lb.id, portId: "http-out" }, { nodeId: second.id, portId: "http-in" });
  link(d, { nodeId: second.id, portId: "cache-out" }, { nodeId: cache.id, portId: "cache-in" });
  link(d, { nodeId: second.id, portId: "sql-out" }, { nodeId: db.id, portId: "sql-in" });
  cache.config.model = { capacityRps: 100 };
  return { d, cache, db, parents: [first, second] };
}

describe("cache-shared-budget", () => {
  it("Shared bounded cache credits only actual hits and SQL backs the rest, independently of node order", () => {
    const { d, cache, db, parents } = fixture();
    db.config.model = { capacity: 0 };
    const before = structuredClone(d);
    for (let i = 0; i < 3; i++) {
      const s = stepSimulation(d);
      near(s.nodes[cache.id].technology.hits, 85); near(s.nodes[db.id].offered, 165); near(s.summary!.completed, 85);
      near(parents.reduce((n, p) => n + s.nodes[p.id].cacheReceipt.cacheHits, 0), 85);
      for (const p of parents) { near(s.nodes[p.id].cacheReceipt.cacheHits, 42.5); near(s.nodes[p.id].outputs["sql-out"], 82.5); }
      d.nodes.reverse(); d.edges.reverse();
    }
    d.nodes = before.nodes; d.edges = before.edges;
    expect(d).toEqual(before);
  });
  it("Service and serverless share receipts, including zero lookup and explicit SQL overrides", () => {
    const { d, cache, db, parents } = fixture("aws-lambda"), f = parents[1];
    let s = stepSimulation(d);
    near(s.nodes[db.id].offered, 165); near(s.nodes[f.id].technology.cacheHits, 42.5); expect(s.nodes[f.id].technology.modelVersion).toBe("serverless-model/1");
    f.config.outputOverrides = { "cache-out": 0 };
    s = stepSimulation(d);
    near(s.nodes[f.id].technology.cacheHits, 0); near(s.nodes[db.id].offered, 165); near(s.nodes[parents[0].id].cacheReceipt.cacheHits, 85);
    f.config.outputOverrides = { "sql-out": 7 };
    s = stepSimulation(d);
    near(s.nodes[f.id].outputs["sql-out"], 7); near(s.nodes[db.id].offered, 89.5); near(s.nodes[cache.id].technology.hits, 85);
  });
  it("Combined load can fail shared cache once per tick; preview never advances counters or history", () => {
    const { d, cache, db } = fixture();
    cache.config.model = { capacityRps: 100, crashThresholdPct: 200, crashAfterTicks: 2 };
    let s = stepSimulation(d);
    expect(s.nodes[cache.id].overloadTicks).toBe(1); near(s.nodes[db.id].offered, 165);
    const before = structuredClone(s), p = previewSimulation(d, s);
    expect(s).toEqual(before); expect(p.nodes[cache.id].overloadTicks).toBe(1); expect(p.samples).toEqual(s.samples); near(p.nodes[db.id].offered, 165);
    s = stepSimulation(d, s);
    expect(s.nodes[cache.id].autoFailed).toBe(true); near(s.nodes[db.id].offered, 250); near(s.nodes[cache.id].technology.hits, 0);
    cache.config.model = { capacityRps: 1000, crashAfterTicks: 2 };
    for (let i = 0; i < 3; i++) s = stepSimulation(d, s);
    expect(s.nodes[cache.id].autoFailed).toBe(false); near(s.nodes[db.id].offered, 37.5);
    modelCommand(s, d, "crash", [cache.id]);
    s = stepSimulation(d, s);
    near(s.nodes[db.id].offered, 250);
  });
  it("Shared accepted fractions and SQL discount are conserved across multiple cache targets and a disabled edge", () => {
    const { d, cache, db, parents } = fixture(), other = createSimulationNode("gcp-memorystore");
    other.config.model = { capacityRps: 50 };
    d.nodes.push(other);
    const extra = link(d, { nodeId: parents[0].id, portId: "cache-out" }, { nodeId: other.id, portId: "cache-in" });
    let s = stepSimulation(d);
    const hits = s.nodes[cache.id].technology.hits + s.nodes[other.id].technology.hits;
    near(parents.reduce((n, p) => n + s.nodes[p.id].cacheReceipt.cacheHits, 0), hits); near(s.nodes[db.id].offered, 250 - hits);
    // Edge cards are rounded to two decimals; receipt accounting retains precision.
    for (const edge of d.edges.filter((e) => e.to.nodeId === cache.id)) {
      const receipt = s.nodes[edge.from.nodeId].cacheReceipt;
      expect(receipt.cacheHits).toBeGreaterThanOrEqual(s.edges[edge.id].accepted * .85 - .005);
    }
    extra.enabled = false;
    s = stepSimulation(d);
    near(s.nodes[other.id].technology.hits, 0); near(s.nodes[db.id].offered, 165);
  });
  it("Virtual dependency cycles are refused without changing stored edges or inventing same-tick credit", () => {
    const node = { id: "handler", type: "service", config: {} }, cache = { id: "cache", type: "redis", config: {} }, db = { id: "db", type: "postgresql", config: {} };
    const edge = (id: string, from: string, to: string, port: string) => ({ id, from: { nodeId: from, portId: port }, to: { nodeId: to, portId: "in" } });
    const edges = [edge("cache-link", "handler", "cache", "cache-out"), edge("sql-link", "handler", "db", "sql-out"), edge("return", "db", "cache", "other")];
    const d: any = { nodes: [node, cache, db], edges }, before = structuredClone(d);
    const plan = planCacheSettlement(d, { order: ["handler", "db", "cache"], edges, delayed: new Set() } as any);
    expect(plan.plans[0].creditAllowed).toBe(false); expect(plan.warnings.length).toBe(1); expect(d).toEqual(before);
  });
  it("Generic Redis also shares its admitted budget rather than predicting separately per caller", () => {
    const { d, cache, db, parents } = fixture();
    cache.type = "redis"; cache.config.model = { capacity: 100, hitRatio: .8 }; db.config.model = { capacity: 0 };
    const s = stepSimulation(d);
    near(s.nodes[cache.id].processed, 100); near(s.nodes[db.id].offered, 170); near(s.summary!.completed, 80);
    for (const p of parents) near(s.nodes[p.id].cacheReceipt.cacheHits, 40);
  });
  it("A real SQL result path back to the shared cache warns and falls back conservatively", () => {
    const d = materializeScenario("cloud-pool-aws-rds"), service = d.nodes.find((n) => n.type === "service")!, pool = d.nodes.find((n) => n.type === "aws-rds")!, etl = d.nodes.find((n) => n.type === "etl-job")!;
    const f = createSimulationNode("aws-lambda"), cache = createSimulationNode("aws-elasticache");
    d.nodes.push(f, cache);
    link(d, { nodeId: service.id, portId: "cache-out" }, { nodeId: cache.id, portId: "cache-in" });
    link(d, { nodeId: etl.id, portId: "event-out" }, { nodeId: f.id, portId: "event-in" });
    link(d, { nodeId: f.id, portId: "cache-out" }, { nodeId: cache.id, portId: "cache-in" });
    const before = structuredClone(d), s = stepSimulation(d);
    expect(s.warnings.some((w: string) => w.includes(service.id) && w.includes("cyclic"))).toBe(true);
    expect(s.nodes[service.id].cacheReceipt.creditAllowed).toBe(false); near(s.nodes[service.id].cacheReceipt.cacheHits, 0); near(s.nodes[pool.id].offered, 250); expect(d).toEqual(before);
  });
  it("A batch of virtual dependencies is rolled back if its combined paths form a cycle", () => {
    const node = { id: "h", type: "service", config: {} }, nodes = [node, ...["c1", "c2", "d1", "d2"].map((id) => ({ id, type: "redis", config: {} }))];
    const edge = (id: string, from: string, to: string, port: string) => ({ id, from: { nodeId: from, portId: port }, to: { nodeId: to, portId: "in" } });
    const edges = [edge("a", "h", "c1", "cache-out"), edge("b", "h", "c2", "cache-out"), edge("c", "h", "d1", "sql-out"), edge("d", "h", "d2", "sql-out"), edge("e", "d1", "c2", "other")];
    const plan = planCacheSettlement({ nodes, edges } as any, { order: ["h", "c1", "d1", "c2", "d2"], edges, delayed: new Set() } as any);
    expect(plan.plans[0].creditAllowed).toBe(false); expect(plan.order.length).toBe(5); expect(new Set(plan.order).size).toBe(5);
  });
});
