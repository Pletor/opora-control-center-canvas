// Převedeno z prototypu `test/simulation.test.mjs`; vynecháno: nic (export/import projektu nahrazen JSON round-tripem modelu).
import { describe, expect, it } from "vitest";
import { catalog } from "../../logic/catalog";
import { type ConnectionPolicy } from "../../logic/connection-policy";
import { connect } from "../../logic/model-rules";
import type { StudioModel } from "../../logic/model-types";
import { createSimulationNode } from "./model-adapter";
import { materializeScenario, scenarios } from "./scenarios";
import { config, resilienceStep, validateModelConfig } from "./simulation-config";
import { createSimulation, modelCommand, stepSimulation } from "./simulation";
import { validateSimulationModel } from "./simulation-validate";

const find = (d: StudioModel, type: string) => d.nodes.find((n) => n.type === type)!;
const model = (n: { config: Record<string, unknown> }) => n.config.model as Record<string, any>;
const sqlEdge = (d: StudioModel) => d.edges.find((e) => e.type === "sql-query")!;

describe("simulation", () => {
  it("Automatické přetížení: souvislý práh, výpadek a obnova po dvou nízkých krocích", () => {
    const d = materializeScenario("web-chain"), service = find(d, "service"), client = find(d, "client");
    Object.assign(model(service), { capacity: 50, crashAfterTicks: 2 });
    let s = stepSimulation(d);
    expect(s.nodes[service.id].overloadTicks).toBe(1);
    expect(s.nodes[service.id].autoFailed).toBe(false);
    s = stepSimulation(d, s);
    expect(s.nodes[service.id].state).toBe("failed");
    expect(s.summary!.completed).toBe(0);
    model(client).rate = 20;
    s = stepSimulation(d, s);
    expect(s.nodes[service.id].state).toBe("recovering");
    expect(s.summary!.completed).toBe(0);
    s = stepSimulation(d, s);
    expect(s.nodes[service.id].autoFailed).toBe(false);
    expect(s.summary!.completed).toBe(20);
    expect(s.nodes[service.id].state).toBe("healthy");
    model(client).rate = 250;
    s = stepSimulation(d, s);
    s = stepSimulation(d, s);
    expect(s.nodes[service.id].autoFailed).toBe(true);
    modelCommand(s, d, "restore-all");
    expect(s.incidents[service.id].kind).toBe("recovering");
    model(client).rate = 20;
    for (let i = 0; i < 3; i++) s = stepSimulation(d, s);
    expect(s.nodes[service.id].state).toBe("healthy");
  });

  it("Resilience neudržuje přerušené přetížení ani nepřebije ruční incident", () => {
    const c = { ...config(find(materializeScenario("web-chain"), "service")), crashAfterTicks: 2 };
    let row: Record<string, any> = resilienceStep(c, {}, 500);
    row = resilienceStep(c, row, 50);
    expect(row.overloadTicks).toBe(0);
    row = resilienceStep(c, row, 500);
    expect(row.autoFailed).toBe(false);
    expect(resilienceStep(c, row, 80).autoState).toBe("stressed");
    expect(resilienceStep(c, row, 150).autoState).toBe("degraded");
    expect(resilienceStep(c, { autoFailed: true }, 0, true).autoFailed).toBe(false);
    const d = materializeScenario("web-chain"), node = find(d, "service");
    model(node).crashAfterTicks = 2;
    let s = stepSimulation(d);
    modelCommand(s, d, "crash", [node.id]);
    for (let i = 0; i < 5; i++) s = stepSimulation(d, s);
    expect(s.nodes[node.id].state).toBe("failed");
    expect(s.incidents[node.id].kind).toBe("crash");
  });

  it("Nové prahové parametry jsou validované a ve výchozím stavu automatické selhání vypnuté", () => {
    const d = materializeScenario("web-chain"), node = find(d, "service");
    model(node).capacity = 1;
    let s = createSimulation();
    for (let i = 0; i < 8; i++) s = stepSimulation(d, s);
    expect(s.nodes[node.id].autoFailed).toBe(false);
    expect(s.nodes[node.id].state).toBe("overloaded");
    expect(() => validateModelConfig({ crashAfterTicks: 1.5 })).toThrow(/celé/);
    expect(() => validateModelConfig({ recoveryTicks: 0 })).toThrow(/parametr/);
  });

  it("Knihovna pokrývá 53 typů a každý scénář je validní, opakovatelný a konečný", () => {
    const types = new Set<string>();
    for (const scenario of scenarios) {
      const d = materializeScenario(scenario.id);
      validateSimulationModel(d);
      for (const node of d.nodes)
        expect(d.edges.some((e) => e.from.nodeId === node.id || e.to.nodeId === node.id), scenario.id + " má nezapojenou komponentu " + node.type).toBe(true);
      let a = createSimulation(), b = createSimulation();
      for (let i = 0; i < 20; i++) {
        const old = structuredClone(a), next = stepSimulation(d, a);
        expect(a, "Krok nesmí změnit předchozí stav.").toEqual(old);
        a = next;
        b = stepSimulation(d, b);
        expect(a).toEqual(b);
        for (const row of Object.values(a.nodes))
          for (const k of ["offered", "processed", "admitted", "rejected", "backlog", "completed"])
            expect(Number.isFinite(row[k]) && row[k] >= 0, scenario.id + " " + k).toBe(true);
        for (const flow of Object.values(a.edges)) expect(Math.abs(flow.offered - flow.accepted - flow.rejected)).toBeLessThan(.03);
      }
      d.nodes.forEach((n) => types.add(n.type));
    }
    expect([...types].sort()).toEqual(catalog.map((c) => c.id).sort());
  });

  it("Client→Frontend→Service→DB: skutečné výpočty toku, výpadek a následná obnova modelu", () => {
    const d = materializeScenario("web-chain"), db = find(d, "postgresql");
    let state = stepSimulation(d);
    expect(state.summary!.completed).toBe(250);
    for (const flow of Object.values(state.edges)) { expect(flow.accepted).toBe(250); expect(flow.response).toBe(250); }
    modelCommand(state, d, "crash", [db.id]);
    state = stepSimulation(d, state);
    expect(state.summary!.completed).toBe(0);
    expect(state.edges[d.edges.at(-1)!.id].rejected).toBe(250);
    modelCommand(state, d, "restore", [db.id]);
    state = stepSimulation(d, state);
    expect(state.nodes[db.id].state).toBe("recovering");
    state = stepSimulation(d, state);
    state = stepSimulation(d, state);
    expect(state.summary!.completed).toBe(250);
    expect(state.events.some((e) => e.kind === "recovery")).toBe(true);
  });

  it("Client concurrency=1 při 12.5 ms omezuje tok na 80, stejně jako doložený referenční experiment", () => {
    const d = materializeScenario("web-chain"), client = find(d, "client");
    model(client).concurrency = 1;
    let s = stepSimulation(d);
    expect(s.summary!.offered).toBe(250);
    expect(s.summary!.completed).toBe(80);
    expect(s.nodes[client.id].rejected).toBe(170);
    for (const edge of Object.values(s.edges)) { expect(edge.accepted).toBe(80); expect(edge.response).toBe(80); }
    model(client).concurrency = 400;
    s = stepSimulation(d);
    expect(s.summary!.completed).toBe(250);
  });

  it("Fronta zachovává jednotky a reaguje na rychlost skutečného navazujícího modelového workeru", () => {
    const d = materializeScenario("queue-backpressure"), q = find(d, "queue"), worker = find(d, "worker");
    let s = stepSimulation(d);
    expect(s.nodes[q.id].backlog).toBe(150);
    expect(s.nodes[worker.id].processed).toBe(100);
    s = stepSimulation(d, s);
    expect(s.nodes[q.id].backlog).toBe(300);
    expect(s.nodes[q.id].offered + s.samples[0].backlog).toBe(s.nodes[q.id].processed + s.nodes[q.id].backlog);
    modelCommand(s, d, "crash", [worker.id]);
    s = stepSimulation(d, s);
    expect(s.nodes[q.id].processed).toBe(0);
    expect(s.nodes[q.id].backlog).toBe(550);
  });

  it("Cache hit ratio redukuje SQL a vypnutá vazba neemituje žádné jednotky", () => {
    const d = materializeScenario("web-overload");
    let s = stepSimulation(d);
    expect(s.edges[sqlEdge(d).id].offered).toBe(50);
    d.edges[0].enabled = false;
    s = stepSimulation(d);
    for (const flow of Object.values(s.edges)) expect(flow.offered).toBe(0);
    expect(s.summary!.completed).toBe(0);
  });

  it("Automaticky selhaná samostatná cache nemůže vykazovat úspěšné hity; SQL fallback respektuje DB", () => {
    const d = materializeScenario("web-overload"), cache = find(d, "redis"), db = find(d, "postgresql");
    Object.assign(model(cache), { crashThresholdPct: 20, crashAfterTicks: 1 });
    const s = stepSimulation(d);
    expect(s.nodes[cache.id].autoFailed).toBe(true);
    expect(s.edges[sqlEdge(d).id].offered).toBe(250);
    expect(s.summary!.completed).toBe(s.nodes[db.id].completed);
    expect(s.summary!.completed).toBe(200);
  });

  it("Řídicí health signály se nepřičítají k HTTP provozu a cyklus má explicitní jednokrokové zpoždění", () => {
    const d = materializeScenario("edge-routing");
    let s = createSimulation();
    for (let i = 0; i < 8; i++) s = stepSimulation(d, s);
    expect(s.summary!.completed).toBe(250);
    expect(find(d, "load-balancer") && s.nodes[find(d, "load-balancer").id].offered).toBe(100);
    const delayed = Object.values(s.edges).filter((e) => e.delayed);
    expect(delayed.length).toBeGreaterThan(0);
    expect(delayed.some((e) => e.offered > 0)).toBe(true);
  });

  it("Breaker opravdu projde closed/open/half-open a vrátí se k plné propustnosti", () => {
    const d = materializeScenario("breaker-recovery"), breaker = find(d, "circuit-breaker"), states = new Set<string>();
    let s = createSimulation();
    for (let i = 0; i < 20; i++) { s = stepSimulation(d, s); states.add(s.nodes[breaker.id].circuit); }
    expect([...states].sort()).toEqual(["closed", "half-open", "open"]);
    expect(s.summary!.completed).toBe(250);
  });

  it("Parametry a plán incidentů přetrvají JSON roundtrip bez dočasného běhu", () => {
    const d = materializeScenario("breaker-recovery");
    const imported = validateSimulationModel(JSON.parse(JSON.stringify(d)));
    expect(imported).toEqual(d);
    expect(imported.modelDefinition!.incidents[0].tick).toBe(3);
    expect("simulationState" in imported).toBe(false);
  });

  it("Dvě fronty sdílející worker neztrácejí odmítnuté doručení", () => {
    const d = materializeScenario("queue-backpressure"), producer = find(d, "event-producer"), worker = find(d, "worker"), q2 = createSimulationNode("queue"), policy = d.modelDefinition.connectionPolicy as ConnectionPolicy;
    d.nodes.push(q2);
    d.edges = connect(d, { nodeId: producer.id, portId: "event-out" }, { nodeId: q2.id, portId: "event-in" }, policy).model.edges;
    d.edges = connect(d, { nodeId: q2.id, portId: "job-out" }, { nodeId: worker.id, portId: "job-in" }, policy).model.edges;
    const s = stepSimulation(d), queues = d.nodes.filter((n) => n.type === "queue");
    expect(queues.reduce((n, q) => n + s.nodes[q.id].backlog, 0)).toBe(150);
    expect(queues.reduce((n, q) => n + s.nodes[q.id].processed, 0)).toBe(100);
    expect(s.nodes[worker.id].processed).toBe(100);
  });

  it("Replika bufferuje přijaté změny; backlog není současně vykázán jako odmítnutí", () => {
    const d = materializeScenario("replica-etl"), replica = find(d, "postgresql-read-replica"), edge = d.edges.find((e) => e.type === "sql-replication")!;
    const s = stepSimulation(d);
    expect(s.edges[edge.id].offered).toBe(125);
    expect(s.edges[edge.id].accepted).toBe(125);
    expect(s.edges[edge.id].rejected).toBe(0);
    expect(s.nodes[replica.id].backlog).toBe(75);
  });

  it("Nedostatečná cache zvýší SQL fallback a respektuje konečnou kapacitu databáze", () => {
    const d = materializeScenario("web-overload"), cache = find(d, "redis");
    model(cache).capacity = 50;
    const s = stepSimulation(d), sql = sqlEdge(d);
    expect(s.edges[sql.id].offered).toBe(210);
    expect(s.edges[sql.id].accepted).toBe(200);
    expect(s.edges[sql.id].rejected).toBe(10);
    expect(s.summary!.completed).toBe(240);
  });

  it("Slow zůstává doloženým incidentem i při současném přetížení", () => {
    const d = materializeScenario("web-chain"), db = find(d, "postgresql");
    let s = stepSimulation(d);
    modelCommand(s, d, "slow", [db.id]);
    s = stepSimulation(d, s);
    expect(s.nodes[db.id].slow).toBe(true);
    expect(s.nodes[db.id].state).toBe("overloaded");
    expect(s.nodes[db.id].latencyMs).toBe(62.5);
    expect(s.summary!.completed).toBe(200);
    expect(s.edges[d.edges.at(-1)!.id].latencyMs).toBeGreaterThan(12.5);
  });
});
