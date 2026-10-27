import { describe, expect, it } from "vitest";
import { emptyStudioModel } from "../../model/logic/model-types";
import { addNode, connectPorts, setParameter, type EditModel } from "./model-edit";
import { modelKey, sameContent, saveProblem } from "./model-save";

const key = (k: string, mods: Partial<{ ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }> = {}) => ({ key: k, ctrlKey: false, metaKey: false, shiftKey: false, ...mods });

describe("model save", () => {
  it("compares content without revision", () => {
    const base: EditModel = addNode(emptyStudioModel("web"), "client", undefined, "c").model;
    expect(sameContent(base, { ...base, revision: 7 })).toBe(true);
    expect(sameContent(base, addNode(base, "service", undefined, "s").model)).toBe(false);
  });

  it("lets a valid model through and names what blocks an invalid one", () => {
    let model: EditModel = addNode(addNode(emptyStudioModel("web"), "client", undefined, "c").model, "load-balancer", undefined, "lb").model;
    const linked = connectPorts(model, { nodeId: "c", portId: "http-out" }, { nodeId: "lb", portId: "http-in" }, "e1");
    if ("model" in linked) model = linked.model;
    expect(saveProblem(model)).toBeNull();
    expect(saveProblem(setParameter(model, "lb", "capacity", -1))).toBe("Neplatný parametr modelu: capacity.");
    expect(saveProblem({ ...model, nodes: model.nodes.map((node) => ({ ...node, name: " " })) })).toBe("Neplatná komponenta.");
    expect(saveProblem({ ...model, modelDefinition: { version: "flow-model/1", layer: "MODEL", principle: "", limitations: "", incidents: [{ tick: 2, kind: "crash", nodeIds: ["gone"] }] } }))
      .toBe("Neplatný plán modelového incidentu.");
  });

  it("maps keys to editing commands but leaves text fields alone", () => {
    expect(modelKey(key("z", { ctrlKey: true }), false)).toBe("undo");
    expect(modelKey(key("Z", { ctrlKey: true, shiftKey: true }), false)).toBe("redo");
    expect(modelKey(key("y", { metaKey: true }), false)).toBe("redo");
    expect(modelKey(key("Delete"), false)).toBe("delete");
    expect(modelKey(key("Escape"), false)).toBe("escape");
    expect(modelKey(key("Backspace"), false)).toBeNull();
    expect(modelKey(key("z", { ctrlKey: true }), true)).toBeNull();
  });
});
