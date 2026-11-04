import { describe, expect, it } from "vitest";
import { compatiblePort, connectionError, edgeFor, pairError, type PairRules, type PortEnd } from "./connection-policy";
import { heartGraph, PROCESS, processGraph, TYPES } from "./flow-fixtures";

const out = (nodeId: string, port = "main") => ({ nodeId, port, direction: "out" as const });
const inp = (nodeId: string, port = "main") => ({ nodeId, port, direction: "in" as const });

describe("connection policy by port kind", () => {
  it("accepts an output to input of the same kind and turns a reversed drag around", () => {
    const graph = heartGraph();
    expect(connectionError(graph, TYPES, out("udalost"), inp("srdce"))).toBeNull();
    expect(connectionError(graph, TYPES, inp("srdce"), out("udalost"))).toBeNull();
  });
  it("rejects self loops, mismatched kinds, duplicates and unknown ports", () => {
    const graph = heartGraph();
    expect(connectionError(graph, TYPES, out("jev"), inp("jev"))).toMatch(/sám se sebou/);
    expect(connectionError(graph, TYPES, out("jev"), inp("srdce", "tool"))).toBe("Nekompatibilní porty: main → tool.");
    expect(connectionError(graph, TYPES, out("jev"), inp("srdce"))).toMatch(/již existuje/);
    expect(connectionError(graph, TYPES, out("jev", "nic"), inp("srdce"))).toBe("Port neexistuje.");
    expect(connectionError(graph, TYPES, out("jev"), out("srdce"))).toMatch(/z výstupu na vstup/);
  });
  it("keeps a cardinality-one port to a single edge", () => {
    const graph = { ...heartGraph(), nodes: [...heartGraph().nodes, { id: "model-2", type: "model.claude" }] };
    expect(connectionError(graph, TYPES, out("model-2", "model"), inp("srdce", "model"))).toMatch(/jen jednu vazbu/);
  });
  it("builds an edge with the kind of the source port and a unique id", () => {
    const graph = { ...heartGraph(), nodes: [...heartGraph().nodes, { id: "nastroj", type: "tool.opora_heart" }] };
    expect(edgeFor(graph, TYPES, inp("srdce", "tool"), out("nastroj", "tool"))).toEqual({ id: "nastroj-srdce-tool", source_node: "nastroj",
      source_port: "tool", target_node: "srdce", target_port: "tool", kind: "tool", label: "" });
    expect(() => edgeFor(graph, TYPES, out("jev"), inp("srdce"))).toThrow(/již existuje/);
  });
  it("finds the matching opposite port for the plus button", () => {
    expect(compatiblePort(TYPES.get("model.claude")!, { kind: "model", direction: "in" })?.name).toBe("model");
    expect(compatiblePort(TYPES.get("tool.opora_heart")!, { kind: "model", direction: "in" })).toBeUndefined();
  });
});

describe("pairError with free-text port types (Studio MODEL)", () => {
  const end = (nodeId: string, direction: "in" | "out", kind: string | null): PortEnd => ({ nodeId, port: "p", direction, kind });
  const rules: PairRules = { exists: () => false };
  it("compares any port type, reports a missing port and runs the extra rule before duplicates", () => {
    expect(pairError(end("a", "out", "sql-query"), end("b", "in", "sql-query"), rules)).toBeNull();
    expect(pairError(end("a", "out", "sql-query"), end("b", "in", "event"), rules)).toBe("Nekompatibilní porty: sql-query → event.");
    expect(pairError(end("a", "out", null), end("b", "in", "event"), { ...rules, missing: "chybí" })).toBe("chybí");
    expect(pairError(end("a", "out", "event"), end("a", "in", "event"), { ...rules, self: "sám" })).toBe("sám");
    expect(pairError(end("a", "out", "event"), end("b", "in", "event"), { exists: () => true, extra: () => "role" })).toBe("role");
    expect(pairError(end("a", "out", "event"), end("b", "in", "event"), { exists: () => true })).toBe("Tato vazba již existuje.");
  });
  it("counts uses only on cardinality-one ports", () => {
    const one: PortEnd = { ...end("b", "in", "event"), cardinality: "one" };
    expect(pairError(end("a", "out", "event"), one, { ...rules, uses: () => 1 })).toMatch(/jen jednu vazbu/);
    expect(pairError(end("a", "out", "event"), { ...one, cardinality: "many" }, { ...rules, uses: () => 1 })).toBeNull();
  });
  it("rejects a drag whose emitted data kind the target does not accept", () => {
    const graph = processGraph();
    expect(connectionError(graph, PROCESS, out("bmi"), inp("oznameni"))).toMatch(/nepřijímá data druhu číslo \(přijímá: text, událost, JSON\)/);
    expect(connectionError(graph, PROCESS, out("formular"), inp("endpoint"))).toBeNull();
  });
});
