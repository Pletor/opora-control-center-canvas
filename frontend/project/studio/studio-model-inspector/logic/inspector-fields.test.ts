import { describe, expect, it } from "vitest";
import { createSimulationNode } from "../../model/simulation/logic/model-adapter";
import { parameterRows, parseParameter } from "./inspector-fields";

describe("inspector fields", () => {
  it("lists the type's simulation parameters with bounds, given value and default", () => {
    const service = createSimulationNode("service", undefined, "s");
    const rows = parameterRows(service);
    expect(rows.map((row) => row.key)).toEqual(["capacity", "latencyMs", "concurrency", "replicas", "telemetryRate", "sqlShare", "eventShare"]);
    expect(rows[0]).toMatchObject({ label: "Kapacita · jednotek / krok", min: 0, max: 100000, value: undefined, fallback: "1000" });
    expect(rows.find((row) => row.key === "telemetryRate")).toMatchObject({ value: 0.01, step: 0.01 });
  });

  it("parses numbers, clears to default and rejects values outside the rules", () => {
    const service = createSimulationNode("service", undefined, "s"), capacity = { key: "capacity" }, replicas = { key: "replicas" };
    expect(parseParameter(service, capacity, " 2500 ")).toEqual({ value: 2500 });
    expect(parseParameter(service, { key: "latencyMs" }, "7,5")).toEqual({ value: 7.5 });
    expect(parseParameter(service, capacity, "")).toEqual({ value: undefined });
    expect(parseParameter(service, capacity, "abc")).toEqual({ error: "Zadejte číslo." });
    expect(parseParameter(service, capacity, "-1")).toEqual({ error: "Neplatný parametr modelu: capacity." });
    expect(parseParameter(service, replicas, "1.5")).toEqual({ error: "replicas musí být celé číslo." });
  });

  it("offers enumerated cloud parameters as options", () => {
    const rows = parameterRows(createSimulationNode("aws-elasticache", undefined, "r"));
    const eviction = rows.find((row) => row.key === "evictionPolicy");
    expect(eviction?.options).toEqual(["lru", "ttl"]);
    expect(parseParameter(createSimulationNode("aws-elasticache", undefined, "r"), eviction!, "ttl")).toEqual({ value: "ttl" });
  });
});
