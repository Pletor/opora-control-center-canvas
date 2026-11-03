import { describe, expect, it } from "vitest";
import { TYPES } from "./flow-fixtures";
import { nodeGlyph, nodeRole, portPlaces, typeLabel } from "./node-role";

describe("node role and port layout come from the registry", () => {
  it("classifies trigger, agent, sub-node and main step", () => {
    expect(nodeRole(TYPES.get("trigger.heart_event"))).toBe("trigger");
    expect(nodeRole(TYPES.get("agent.claude"))).toBe("agent");
    expect(nodeRole(TYPES.get("model.claude"))).toBe("sub");
    expect(nodeRole(TYPES.get("decision.jev"))).toBe("main");
    expect(nodeRole(undefined)).toBe("main");
  });
  it("puts main ports left and right and sub-ports at the bottom with a required model", () => {
    const places = portPlaces(TYPES.get("agent.claude"));
    expect(places.map((p) => [p.name, p.direction, p.side, p.label, p.required])).toEqual([
      ["main", "in", "left", "", false], ["main", "out", "right", "", false],
      ["model", "in", "bottom", "Model", true], ["tool", "in", "bottom", "Nástroj", false], ["memory", "in", "bottom", "Paměť", false]]);
    expect(places.filter((p) => p.side === "bottom").map((p) => p.offset)).toEqual([0.25, 0.5, 0.75]);
  });
  it("labels named outputs and gives sub-nodes a top port", () => {
    expect(portPlaces(TYPES.get("approval.human")).filter((p) => p.direction === "out").map((p) => p.label)).toEqual(["approved", "rejected", "timeout"]);
    expect(portPlaces(TYPES.get("model.claude"))[0]).toMatchObject({ side: "top", label: "Model" });
  });
  it("picks glyphs and readable names", () => {
    expect(nodeGlyph(TYPES.get("model.claude"))).toBe("M");
    expect(nodeGlyph(TYPES.get("approval.human"))).toBe("?");
    expect(typeLabel("trigger.heart_event")).toEqual({ family: "trigger", name: "heart event" });
  });
});
