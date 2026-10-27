// Převedeno z prototypu `test/cloud-edge.test.mjs`; vynecháno: `exportProject`/`importProject` projektu (nahrazeno JSON
// round-tripem modelu přes `validateSimulationModel`). Soubor `analysis/evidence/extended-catalog-observations.json`
// se za běhu nečte, jeho hodnoty jsou v `cloud-edge-evidence.ts`.
import { describe, expect, it } from "vitest";
import { cloudCatalog } from "../../logic/catalog-cloud";
import { observedCloudItems } from "./cloud-edge-evidence";
import { materializeScenario } from "./scenarios";
import { modelCommand, previewSimulation, stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";

type Cfg = Record<string, any>;
const caches = cloudCatalog.filter((c) => c.cloudProfile === "edge-cache");
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);

describe("cloud-edge", () => {
  it("Provider identities, defaults and ports match independently retained source observations", () => {
    expect(cloudCatalog.length).toBe(30);
    expect(caches.length).toBe(3);
    for (const c of cloudCatalog) {
      const source = observedCloudItems.find((i) => i.id === c.id)!;
      expect(c.provider).toBe(source.provider);
      expect(c.ports).toEqual(source.ports);
      expect(c.sourceDefaults).toEqual(source.defaults);
    }
  });

  it("Provider cache/shield reductions conserve requests and capacity, without a connected origin no missing requests are invented", () => {
    for (const c of caches) {
      const sd = c.sourceDefaults as Cfg;
      const d = materializeScenario("cloud-edge-" + c.id), edge = d.nodes.find((n) => n.type === c.id)!, expectedOrigin = 250 * (1 - sd.edgeHitRate) * (1 - sd.originShieldRate);
      let s = stepSimulation(d), r = s.nodes[edge.id];
      near(r.technology.originRequests, expectedOrigin);
      near(r.technology.edgeHits + r.technology.shieldHits + expectedOrigin, 250);
      near(s.summary!.completed, 250);
      d.edges = d.edges.filter((e) => e.from.nodeId !== edge.id);
      s = stepSimulation(d);
      r = s.nodes[edge.id];
      near(s.summary!.completed, 250 - expectedOrigin);
      expect(r.technology.lastOriginSuccessTick).toBe(null);
      near(r.technology.staleServed, 0);
      const partial = materializeScenario("cloud-edge-" + c.id);
      (partial.nodes.find((n) => n.type === "frontend-app")!.config.model as Cfg).capacity = 5;
      const limited = stepSimulation(partial);
      near(limited.summary!.completed, 250 - expectedOrigin + 5);
      expect(limited.nodes[partial.nodes.find((n) => n.type === c.id)!.id].technology.lastOriginSuccessTick).toBe(null);
    }
  });

  it("Stale expiry uses committed model seconds, requires a successful origin and recovers after actual model restoration", () => {
    for (const c of caches) {
      const d = materializeScenario("cloud-edge-" + c.id), edge = d.nodes.find((n) => n.type === c.id)!, origin = d.nodes.find((n) => n.type === "frontend-app")!;
      edge.config.model = { staleWhileRevalidateSeconds: 1 };
      let s = stepSimulation(d);
      expect(s.nodes[edge.id].technology.lastOriginSuccessTick).toBe(1);
      modelCommand(s, d, "crash", [origin.id]);
      s = stepSimulation(d, s);
      const missing = s.nodes[edge.id].technology.originRequests;
      near(s.nodes[edge.id].technology.staleServed, missing);
      near(s.summary!.completed, 250);
      const before = structuredClone(s), preview = previewSimulation(d, s);
      expect(s).toEqual(before);
      expect(preview.tick).toBe(2);
      expect(preview.nodes[edge.id].technology.staleAgeSeconds).toBe(1);
      s = stepSimulation(d, s);
      near(s.nodes[edge.id].technology.staleServed, 0);
      near(s.summary!.completed, 250 - missing);
      modelCommand(s, d, "restore-all");
      for (let i = 0; i < 3; i++) s = stepSimulation(d, s);
      near(s.summary!.completed, 250);
      expect(s.nodes[edge.id].technology.staleAgeSeconds).toBe(0);
    }
  });

  it("Cloud definitions persist provider identity and overrides without volatile cache warm state", () => {
    const d = materializeScenario("cloud-edge-aws-cloudfront"), edge = d.nodes.find((n) => n.type === "aws-cloudfront")!;
    edge.config.model = { edgeCapacityRps: 100, edgeHitRate: 1 };
    const serialized = JSON.stringify(d), restored = validateSimulationModel(JSON.parse(serialized));
    expect(restored).toEqual(d);
    expect(serialized.includes("lastOriginSuccessTick")).toBe(false);
    const a = stepSimulation(d), b = stepSimulation(restored);
    expect(a).toEqual(b);
    near(a.nodes[edge.id].processed, 100);
    near(a.summary!.completed, 100);
    near(a.nodes[edge.id].technology.originRequests, 0);
  });
});
