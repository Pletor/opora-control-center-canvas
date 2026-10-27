import { describe, expect, it } from "vitest";
import { materializeScenario } from "../../model/simulation/logic";
import type { EditModel } from "../../studio-model/logic/model-edit";
import { advanceRun, clampSpeed, commandRun, incidentNodes, initialRun, resetRun, runSignature, runTouched, tickDelayMs } from "./run-control";

const chain = (): EditModel => materializeScenario("web-chain", "scenario:web-chain");

describe("run control", () => {
  it("keeps speed in 0.25–5× and turns it into the delay of one model second", () => {
    expect(clampSpeed(10)).toBe(5);
    expect(clampSpeed(0.1)).toBe(0.25);
    expect(clampSpeed(Number.NaN)).toBe(1);
    expect(tickDelayMs(1)).toBe(1000);
    expect(tickDelayMs(5)).toBe(200);
    expect(tickDelayMs(0.25)).toBe(4000);
  });

  it("advances one tick over the current model and records history", () => {
    const model = chain();
    let run = advanceRun(model, initialRun());
    run = advanceRun(model, run);
    expect(run.sim.tick).toBe(2);
    expect(run.sim.summary!.completed).toBe(250);
    expect(run.history.summary.map((s) => s.tick)).toEqual([1, 2]);
    expect(run.history.nodes.service).toHaveLength(2);
    expect(runTouched(run)).toBe(true);
  });

  it("applies an incident at once without moving time, and restores", () => {
    const model = chain();
    const before = advanceRun(model, initialRun());
    const crashed = commandRun(model, before, "crash", ["service"]);
    expect(crashed.sim.tick).toBe(1);
    expect(crashed.sim.nodes.service.state).toBe("failed");
    expect(crashed.history).toBe(before.history);
    expect(before.sim.nodes.service.state).toBe("healthy");
    expect(incidentNodes(crashed.sim)).toEqual(["service"]);
    const restored = commandRun(model, crashed, "restore", ["service"]);
    expect(restored.sim.incidents.service.kind).toBe("recovering");
  });

  it("toggles surge and reports a broken command instead of throwing", () => {
    const model = chain();
    const surged = commandRun(model, initialRun(), "surge");
    expect(surged.sim.surge).toBe(5);
    expect(commandRun(model, initialRun(), "crash", ["missing"]).error).toMatch(/Incident nejde použít/);
  });

  it("stops the run with a reason when the model cannot be computed", () => {
    const model = chain();
    const broken = { ...model, nodes: model.nodes.map((n) => n.id === "service" ? { ...n, type: "no-such-type" } : n) };
    const run = advanceRun(broken, { ...initialRun(), running: true });
    expect(run.running).toBe(false);
    expect(run.error).toMatch(/Model nejde spočítat/);
  });

  it("reset keeps speed only", () => {
    const run = advanceRun(chain(), initialRun(2));
    const reset = resetRun(run);
    expect(reset.sim.tick).toBe(0);
    expect(reset.speed).toBe(2);
    expect(runTouched(reset)).toBe(false);
  });

  it("signature ignores position, name and planned incidents but not configuration", () => {
    const model = chain(), base = runSignature(model);
    const moved = { ...model, nodes: model.nodes.map((n) => ({ ...n, position: { x: 1, y: 2 }, name: n.name + "!" })) };
    expect(runSignature(moved)).toBe(base);
    expect(runSignature({ ...model, modelDefinition: { ...model.modelDefinition!, incidents: [{ tick: 3, kind: "crash", nodeIds: ["db"] }] } })).toBe(base);
    const tuned = { ...model, nodes: model.nodes.map((n) => n.id === "service" ? { ...n, config: { model: { capacity: 10 } } } : n) };
    expect(runSignature(tuned)).not.toBe(base);
    expect(runSignature({ ...model, edges: model.edges.slice(1) })).not.toBe(base);
  });
});
