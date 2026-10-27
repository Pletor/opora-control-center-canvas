import { describe, expect, it } from "vitest";
import { emptyStudioModel } from "../../model/logic/model-types";
import { addNode, connectPorts, moveNode, placeNew, portDirection, removeSelected, renameNode, setBinding, setParameter, updateEdge, type EditModel } from "./model-edit";

function webModel() {
  let model: EditModel = emptyStudioModel("web");
  for (const [type, id] of [["client", "c"], ["load-balancer", "lb"], ["service", "s"], ["postgresql", "db"]]) model = addNode(model, type, undefined, id).model;
  return model;
}

describe("model edit", () => {
  it("adds catalog components with simulation defaults on free grid slots and unique names", () => {
    const model = addNode(webModel(), "service", undefined, "s2").model;
    expect(model.nodes.map((node) => node.position)).toEqual([{ x: 80, y: 80 }, { x: 380, y: 80 }, { x: 680, y: 80 }, { x: 980, y: 80 }, { x: 80, y: 360 }]);
    expect(model.nodes.find((node) => node.id === "s")!.config.model).toEqual({ telemetryRate: 0.01 });
    expect(model.nodes.find((node) => node.id === "s2")!.name).toBe("Service 2");
    expect(placeNew(moveNode(model, "c", { x: 2000, y: 2000 }))).toEqual({ x: 80, y: 80 });
  });

  it("connects output to input and explains forbidden links without changing the model", () => {
    const model = webModel();
    const ok = connectPorts(model, { nodeId: "c", portId: "http-out" }, { nodeId: "lb", portId: "http-in" }, "e1");
    expect("model" in ok && ok.model.edges[0]).toMatchObject({ id: "e1", type: "http-request", enabled: true });
    const wrong = connectPorts(model, { nodeId: "c", portId: "http-out" }, { nodeId: "db", portId: "sql-in" });
    expect(wrong).toEqual({ error: "Nekompatibilní porty: http-request → sql-query." });
    expect(model.edges).toEqual([]);
    expect(portDirection(model, { nodeId: "db", portId: "sql-in" })).toBe("input");
    expect(portDirection(model, { nodeId: "db", portId: "nope" })).toBeNull();
  });

  it("removes a node with its edges and incident references, or a single edge", () => {
    let model = webModel();
    for (const [from, out, to, input, id] of [["c", "http-out", "lb", "http-in", "e1"], ["lb", "http-out", "s", "http-in", "e2"], ["s", "sql-out", "db", "sql-in", "e3"]]) {
      const result = connectPorts(model, { nodeId: from, portId: out }, { nodeId: to, portId: input }, id);
      if ("model" in result) model = result.model;
    }
    model = { ...model, modelDefinition: { version: "flow-model/1", layer: "MODEL", principle: "", limitations: "", incidents: [{ tick: 3, kind: "crash", nodeIds: ["s"] }, { tick: 4, kind: "slow", nodeIds: ["s", "db"] }] } };
    const without = removeSelected(model, { kind: "node", id: "s" });
    expect(without.edges.map((edge) => edge.id)).toEqual(["e1"]);
    expect(without.modelDefinition!.incidents).toEqual([{ tick: 4, kind: "slow", nodeIds: ["db"] }]);
    expect(removeSelected(model, { kind: "edge", id: "e2" }).edges.map((edge) => edge.id)).toEqual(["e1", "e3"]);
    expect(removeSelected(model, null)).toBe(model);
  });

  it("renames, binds, sets and clears parameters and patches edges", () => {
    let model = webModel();
    model = renameNode(model, "s", "Objednávky");
    model = setBinding(model, "s", "card-1");
    expect(model.nodes.find((node) => node.id === "s")).toMatchObject({ name: "Objednávky", binding: { nodeId: "card-1" } });
    expect(setBinding(model, "s", null).nodes.find((node) => node.id === "s")!.binding).toBeUndefined();
    model = setParameter(model, "s", "capacity", 500);
    expect(model.nodes.find((node) => node.id === "s")!.config.model).toEqual({ telemetryRate: 0.01, capacity: 500 });
    model = setParameter(setParameter(model, "s", "capacity", undefined), "s", "telemetryRate", undefined);
    expect("model" in model.nodes.find((node) => node.id === "s")!.config).toBe(false);
    const linked = connectPorts(model, { nodeId: "c", portId: "http-out" }, { nodeId: "lb", portId: "http-in" }, "e1");
    if (!("model" in linked)) throw new Error(linked.error);
    expect(updateEdge(linked.model, "e1", { enabled: false, label: "GET /" }).edges[0]).toMatchObject({ enabled: false, label: "GET /" });
  });
});
