// Převedeno z prototypu `test/cloud-cache.test.mjs` (první polovina; zbytek v `cloud-cache-2.test.ts`); nic nevynecháno.
import { describe, expect, it } from "vitest";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";

const types = ["aws-elasticache", "gcp-memorystore", "aliyun-tair"];
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

function fixture(type: string) {
  const d = materializeScenario("cloud-cache-" + type);
  return { d, cache: d.nodes.find((n) => n.type === type)!, db: d.nodes.find((n) => n.type === "postgresql")!, service: d.nodes.find((n) => n.type === "service")! };
}

describe("cloud-cache", () => {
  it("All provider cache-aside paths use observed baseline hits and offer only accepted misses to SQL", () => {
    for (const [type, hit] of types.map((t, i) => [t, [.85, .84, .88][i]] as const)) {
      const { d, cache, db } = fixture(type), s = stepSimulation(d), m = s.nodes[cache.id].technology;
      near(m.offered, 250);
      near(m.processed, 250);
      near(m.hits, 250 * hit);
      near(m.misses, 250 * (1 - hit));
      near(m.fallback, 0);
      near(s.nodes[db.id].offered, 250 * (1 - hit));
      near(s.summary!.completed, 250);
      expect(stepSimulation(d)).toEqual(s);
      expect(m.modelVersion).toBe("cache-model/1");
    }
  });

  it("Actual memory/TTL model edits change the same cache hit and SQL fallback volumes without advancing preview time", () => {
    const { d, cache, db } = fixture("aws-elasticache");
    let s = stepSimulation(d);
    for (const [patch, hit] of [[{ memoryLimitMb: 512 }, .595], [{ ttlSeconds: 0 }, .2975], [{ memoryLimitMb: 512, ttlSeconds: 0 }, .20825], [{ ttlSeconds: 30 }, .425]] as const) {
      cache.config.model = patch;
      const before = structuredClone(s), p = previewSimulation(d, s);
      expect(s).toEqual(before);
      expect(p.tick).toBe(s.tick);
      near(p.nodes[cache.id].technology.hits, 250 * hit);
      near(p.nodes[db.id].offered, 250 * (1 - hit));
      s = stepSimulation(d, s);
      near(s.nodes[db.id].offered, 250 * (1 - hit));
    }
  });

  it("Capacity throttling, manual and automatic cache failures fall back to actual SQL capacity and recover", () => {
    const { d, cache, db } = fixture("aws-elasticache");
    cache.config.model = { capacityRps: 100 };
    let s = stepSimulation(d);
    near(s.nodes[cache.id].processed, 100);
    near(s.nodes[cache.id].technology.hits, 85);
    near(s.nodes[cache.id].technology.misses, 15);
    near(s.nodes[cache.id].technology.fallback, 150);
    near(s.nodes[db.id].offered, 165);
    near(s.summary!.completed, 250);
    modelCommand(s, d, "crash", [cache.id]);
    s = stepSimulation(d, s);
    near(s.nodes[db.id].offered, 250);
    near(s.nodes[cache.id].technology.hits, 0);
    near(s.nodes[cache.id].technology.fallback, 250);
    modelCommand(s, d, "restore", [cache.id]);
    for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
    near(s.nodes[db.id].offered, 165);
    cache.config.model = { capacityRps: 100, crashThresholdPct: 200, crashAfterTicks: 1 };
    s = stepSimulation(d);
    expect(s.nodes[cache.id].autoFailed).toBe(true);
    near(s.nodes[cache.id].technology.hits, 0);
    near(s.nodes[db.id].offered, 250);
    db.config.model = { capacity: 50 };
    s = stepSimulation(d);
    near(s.summary!.completed, 50);
  });

  it("Cache hits remain useful when SQL fails, but a simultaneous cache outage cannot manufacture completion", () => {
    for (const type of types) {
      const { d, cache, db } = fixture(type);
      let s = stepSimulation(d);
      const hits = s.nodes[cache.id].technology.hits;
      modelCommand(s, d, "crash", [db.id]);
      s = stepSimulation(d, s);
      near(s.summary!.completed, hits);
      modelCommand(s, d, "crash", [cache.id]);
      s = stepSimulation(d, s);
      near(s.summary!.completed, 0);
      modelCommand(s, d, "restore-all");
      for (let i = 0; i < 4; i++) s = stepSimulation(d, s);
      near(s.summary!.completed, 250);
    }
  });
});

