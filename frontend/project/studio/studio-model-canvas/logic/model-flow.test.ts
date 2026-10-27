import { describe, expect, it } from "vitest";
import { emptyStudioModel } from "../../model/logic/model-types";
import { addNode, connectPorts, moveNode, setBinding, updateEdge, type EditModel } from "../../studio-model/logic/model-edit";
import { portKey } from "./connect-gesture";
import { modelCards, modelFlowNodes, modelLayout, modelLinks } from "./model-flow";

function linked(): EditModel {
  let model: EditModel = emptyStudioModel("web");
  model = addNode(model, "client", { x: 0, y: 0 }, "c").model;
  model = addNode(model, "load-balancer", { x: 400, y: 0 }, "lb").model;
  model = addNode(model, "kubernetes-deployment", { x: 0, y: 400 }, "k8s").model;
  const result = connectPorts(model, { nodeId: "c", portId: "http-out" }, { nodeId: "lb", portId: "http-in" }, "e1");
  if (!("model" in result)) throw new Error(result.error);
  return result.model;
}

describe("model flow", () => {
  it("sizes cards by measured geometry and turns linked ports towards each other", () => {
    const model = linked(), layout = modelLayout(model);
    expect(layout.nodes.find((node) => node.id === "k8s")).toMatchObject({ width: 518, height: 309 });
    expect(layout.ports.get("c")!.get("http-out")!.side).toBe("right");
    expect(layout.ports.get("lb")!.get("http-in")!.side).toBe("left");
    const moved = modelLayout(model, new Map([["lb", { x: 0, y: -600 }]]));
    expect(moved.nodes.find((node) => node.id === "lb")).toMatchObject({ x: 0, y: -600 });
    expect(moved.ports.get("c")!.get("http-out")!.side).toBe("top");
  });

  it("describes cards with typed port colours, link targets and the bound OPORA card", () => {
    const model = setBinding(setBinding(linked(), "c", "home"), "lb", "gone"), layout = modelLayout(model);
    const targets = new Map([[portKey({ nodeId: "lb", portId: "http-in" }), "compatible" as const]]);
    const bindings = new Map([["home", { id: "home", name: "Domů", kindLabel: "Stránka", state: "done" as const, stateLabel: "hotovo" }]]);
    const [client, balancer] = modelCards(model, layout, { pending: portKey({ nodeId: "c", portId: "http-out" }), targets, bindings });
    expect(client).toMatchObject({ name: "Client", typeName: "Client", icon: "▣", group: "Web", stages: ["Záměr", "Souběh", "Odpověď"], binding: { name: "Domů", state: "done" } });
    expect(client.ports[0]).toMatchObject({ id: "http-out", color: "#38d996", connected: 1, pending: true, side: "right" });
    expect(balancer.ports.find((port) => port.id === "http-in")).toMatchObject({ color: "#49b8ff", target: "compatible" });
    expect(balancer.binding).toEqual({ name: "gone", state: "missing", stateLabel: "karta chybí" });
    const nodes = modelFlowNodes([client, balancer], layout, { kind: "node", id: "lb" });
    expect(nodes[1]).toMatchObject({ id: "lb", type: "model-card", position: { x: 400, y: 0 }, selected: true });
  });

  it("draws links coloured by type, dimmed when disabled, with a midpoint for the label", () => {
    const model = updateEdge(moveNode(linked(), "lb", { x: 400, y: 0 }), "e1", { enabled: false, label: "GET" });
    const [link] = modelLinks(model, modelLayout(model), { kind: "edge", id: "e1" });
    expect(link).toMatchObject({ id: "e1", color: "#49b8ff", inactive: true, selected: true, label: "GET" });
    expect(link.d.startsWith("M ")).toBe(true);
    expect(Number.isFinite(link.mid.x)).toBe(true);
  });
});
