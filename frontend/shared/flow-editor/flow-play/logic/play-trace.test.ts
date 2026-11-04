import { describe, expect, it } from "vitest";
import { processGraph } from "../../logic/flow-fixtures";
import { dataLabel, nextIndex, routeText, simulateError, stepEdge, stepMs, verdict, type SimulateResponse, type TraceStep } from "./play-trace";

const step = (nodeId: string, edgeId?: string): TraceStep => ({ step: 0, nodeId, edgeId, layer: "be", type: "be.function", in: {}, out: {}, note: "" });

describe("play trace", () => {
  it("walks forward and back and reports the ends as null", () => {
    expect(nextIndex(0, 3, 1)).toBe(1);
    expect(nextIndex(2, 3, 1)).toBeNull();
    expect(nextIndex(0, 3, -1)).toBeNull();
    expect(nextIndex(2, 3, -1)).toBe(1);
    expect(nextIndex(0, 0, 1)).toBeNull();
  });

  it("flies along the edgeId of the step, else along the edge between consecutive nodes", () => {
    const graph = processGraph();
    expect(stepEdge(graph, [step("formular"), step("tlacitko", "e1")], 1)).toBe("e1");
    expect(stepEdge(graph, [step("formular"), step("tlacitko")], 1)).toBe("e1");
    expect(stepEdge(graph, [step("formular"), step("oznameni")], 1)).toBeNull();
    expect(stepEdge(graph, [step("formular")], 0)).toBeNull();
  });

  it("shortens the data label to compact JSON", () => {
    expect(dataLabel({ vyska: 180, vaha: 80 })).toBe('{"vyska":180,"vaha":80}');
    expect(dataLabel({ text: "x".repeat(80) }, 20)).toHaveLength(20);
    expect(dataLabel({ text: "x".repeat(80) }, 20).endsWith("…")).toBe(true);
    expect(dataLabel("ahoj")).toBe("ahoj");
    expect(dataLabel(undefined)).toBe("");
  });

  it("speeds divide the step time", () => {
    expect(stepMs(2)).toBe(stepMs(1) / 2);
    expect(stepMs(4)).toBe(stepMs(1) / 4);
  });

  it("states the verdict against expect and prints the route", () => {
    const base: SimulateResponse = { ok: true, result: null, trace: [step("a"), step("b")], expect: null };
    expect(verdict(base).tone).toBe("idle");
    expect(verdict({ ...base, expect: { ok: true, diffs: [] } }).tone).toBe("ok");
    expect(verdict({ ...base, expect: { ok: false, diffs: ["bmi: čekáno 24,7, vyšlo 25"] } }).tone).toBe("fail");
    expect(routeText(base.trace)).toBe("a → b");
  });

  it("explains a refused case and an outage in plain words", () => {
    expect(simulateError(Object.assign(new Error("HTTP 422"), { status: 422, body: { detail: "start neexistuje" } }))).toBe("Simulace případ odmítla: start neexistuje");
    expect(simulateError(new Error("Failed to fetch"))).toBe("Simulaci se nepodařilo spustit: Failed to fetch");
  });
});
