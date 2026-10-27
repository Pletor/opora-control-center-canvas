// Převedeno z prototypu `test/cloud-pool.test.mjs`; vynecháno: `exportProject`/`importProject` projektu
// (nahrazeno JSON round-tripem modelu přes `validateSimulationModel`).
import { describe, expect, it } from "vitest";
import { connect, connectionError } from "../../logic/model-rules";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";

const types = ["aws-rds", "gcp-cloud-sql", "aliyun-polardb"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

function fixture(type: string) {
  const d = materializeScenario("cloud-pool-" + type);
  return { d, pool: d.nodes.find((n) => n.type === type)!, etl: d.nodes.find((n) => n.type === "etl-job")!, replica: d.nodes.find((n) => n.type === "postgresql-read-replica")! };
}

describe("cloud-pool", () => {
  it("Provider SQL graphs apply exact served admission and send distinct result and commit volumes to actual consumers", () => {
    for (const type of types) {
      const { d, pool, etl, replica } = fixture(type), s = stepSimulation(d), total = type === "aliyun-polardb" ? 249 : 248.5, commits = total - 200;
      near(s.nodes[pool.id].processed, total);
      near(s.summary!.completed, total);
      near(s.nodes[etl.id].offered, total);
      near(s.nodes[etl.id].processed, total);
      near(s.nodes[replica.id].technology.received, commits);
      near(s.nodes[replica.id].technology.applied, commits);
      near(s.nodes[replica.id].technology.queryProcessed, 0);
      near(s.nodes[replica.id].technology.lag, 0);
      near(s.edges[d.edges.find((e) => e.type === "sql-replication")!.id].accepted, commits);
      expect(stepSimulation(d)).toEqual(s);
    }
  });

  it("Pool1 and independent read100/write10 cases use resource pressure and source latency before resilience", () => {
    const { d, pool } = fixture("aws-rds");
    pool.config.model = { maxConnections: 1 };
    let s = stepSimulation(d);
    near(s.nodes[pool.id].processed, 71);
    near(s.nodes[pool.id].pressurePct, 100);
    near(s.nodes[pool.id].latencyMs, 12000);
    for (let i = 0; i < 6; i++) s = stepSimulation(d, s);
    expect(s.nodes[pool.id].autoFailed).toBe(false);
    pool.config.model = { readCapacityRps: 100, writeCapacityTps: 10 };
    s = stepSimulation(d);
    near(s.nodes[pool.id].processed, 109.7);
    near(s.nodes[pool.id].pressurePct, 500);
    near(s.nodes[pool.id].latencyMs, 12000);
    s = stepSimulation(d, s);
    s = stepSimulation(d, s);
    expect(s.nodes[pool.id].autoFailed).toBe(true);
    near(s.nodes[pool.id].processed, 0);
    pool.config.model = {};
    s = stepSimulation(d, s);
    s = stepSimulation(d, s);
    near(s.nodes[pool.id].processed, 248.5);
    expect(s.nodes[pool.id].autoFailed).toBe(false);
  });

  it("Manual source-observed Recover keeps preview unavailable and resumes on the next committed Step without affecting old restore contracts", () => {
    for (const type of types) {
      const { d, pool, etl, replica } = fixture(type);
      let s = stepSimulation(d);
      modelCommand(s, d, "crash", [pool.id]);
      s = stepSimulation(d, s);
      near(s.nodes[pool.id].processed, 0);
      near(s.nodes[etl.id].offered, 0);
      near(s.nodes[replica.id].technology.received, 0);
      modelCommand(s, d, "restore", [pool.id]);
      const before = structuredClone(s), preview = previewSimulation(d, s);
      expect(s).toEqual(before);
      expect(preview.nodes[pool.id].state).toBe("recovering");
      near(preview.nodes[pool.id].processed, 0);
      s = stepSimulation(d, s);
      expect(s.nodes[pool.id].state).toBe("healthy");
      near(s.nodes[pool.id].processed, type === "aliyun-polardb" ? 249 : 248.5);
      expect(s.events.some((e) => e.kind === "recovery")).toBe(true);
    }
    const { d, etl } = fixture("aws-rds");
    let s = stepSimulation(d);
    modelCommand(s, d, "crash", [etl.id]);
    s = stepSimulation(d, s);
    modelCommand(s, d, "restore", [etl.id]);
    s = stepSimulation(d, s);
    expect(s.nodes[etl.id].state).toBe("recovering");
    near(s.nodes[etl.id].processed, 0);
  });

  it("Isolation and zero read-time source cases are immediate pure previews with unchanged committed history", () => {
    const { d, pool } = fixture("aws-rds");
    let s = stepSimulation(d);
    for (const [isolationLevel, total] of [["serializable", 210], ["repeatable-read", 218.75]] as const) {
      pool.config.model = { isolationLevel, lockContention: .5 };
      const before = structuredClone(s), p = previewSimulation(d, s);
      expect(s).toEqual(before);
      near(p.nodes[pool.id].processed, total);
      expect(p.tick).toBe(s.tick);
      expect(p.samples).toEqual(s.samples);
      s = stepSimulation(d, s);
      near(s.nodes[pool.id].processed, total);
    }
    pool.config.model = { readLatencyMs: 0 };
    s = stepSimulation(d);
    near(s.nodes[pool.id].latencyMs, 0);
    near(s.nodes[pool.id].processed, 248.5);
  });

  it("Result consumer failure does not invent transaction rollback and replica receipt/lag is explicitly observable", () => {
    const { d, pool, etl, replica } = fixture("aws-rds");
    replica.config.model = { capacity: 10, buffer: 100 };
    let s = stepSimulation(d);
    near(s.nodes[replica.id].technology.applied, 10);
    near(s.nodes[replica.id].technology.lag, 38.5);
    modelCommand(s, d, "crash", [etl.id]);
    s = stepSimulation(d, s);
    near(s.nodes[pool.id].processed, 248.5);
    near(s.nodes[pool.id].technology.writeCommitted, 48.5);
    near(s.nodes[etl.id].processed, 0);
    near(s.edges[d.edges.find((e) => e.type === "sql-result")!.id].rejected, 248.5);
    near(s.summary!.completed, 248.5);
    expect(s.nodes[replica.id].technology.lag).toBeGreaterThan(38.5);
  });

  it("Multiple actual SQL callers share served volume proportionally without double allocating the pool", () => {
    const { d, pool } = fixture("aws-rds"), lb = d.nodes.find((n) => n.type === "load-balancer")!, other = createSimulationNode("service");
    d.nodes.push(other);
    d.edges.push(connect(d, { nodeId: lb.id, portId: "http-out" }, { nodeId: other.id, portId: "http-in" }).edge);
    d.edges.push(connect(d, { nodeId: other.id, portId: "sql-out" }, { nodeId: pool.id, portId: "sql-in" }).edge);
    const s = stepSimulation(d);
    near(s.nodes[pool.id].offered, 250);
    near(s.nodes[pool.id].processed, 248.5);
    const calls = d.edges.filter((e) => e.to.nodeId === pool.id);
    expect(calls.length).toBe(2);
    for (const e of calls) {
      near(s.edges[e.id].offered, 125);
      near(s.edges[e.id].accepted, 124.25);
    }
    near(s.summary!.completed, 248.5);
  });

  it("Pool definitions preserve source enum/zero-duration settings and IDs while rejecting bad ports, bounds and runtime leakage", () => {
    for (const type of types) {
      const { d, pool, etl } = fixture(type);
      pool.config.model = { readLatencyMs: 0, maxConnections: 2, isolationLevel: "serializable", lockContention: .5 };
      const raw = JSON.stringify(d);
      expect(validateSimulationModel(JSON.parse(raw))).toEqual(d);
      expect(raw.includes("activeConnections")).toBe(false);
      expect(raw.includes("writeCommitted")).toBe(false);
      expect(connectionError(d, { nodeId: pool.id, portId: "replication-out" }, { nodeId: etl.id, portId: "sql-result-in" })).toBeTruthy();
      for (const patch of [{ maxConnections: 0 }, { maxConnections: 1.5 }, { isolationLevel: "unsafe" }, { readRatio: 2 }, { lockContention: .6 }, { readLatencyMs: -1 }]) {
        pool.config.model = patch;
        expect(() => validateSimulationModel(d)).toThrow();
      }
    }
  });
});
