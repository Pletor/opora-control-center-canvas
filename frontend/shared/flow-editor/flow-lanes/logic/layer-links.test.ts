import { describe, expect, it } from "vitest";
import { nodeTypeMap, type FlowGraph, type NodeTypeSpec } from "../../logic/flow-types";
import { defaultVia, layersLinkable, linkableTypes, settleAdded } from "./layer-links";

const step = [{ name: "main", direction: "in" as const, kind: "main" as const, cardinality: "many" as const }, { name: "main", direction: "out" as const, kind: "main" as const, cardinality: "many" as const }];
const spec = (type: string, layer?: NodeTypeSpec["layer"]): NodeTypeSpec => ({ type, version: 1, trigger: false, ports: step, ...(layer ? { layer } : {}) });
const specs = [spec("fe.click", "fe"), spec("be.function", "be"), spec("db.write", "db"), spec("infra.api", "infra"), spec("transform.set", "neutral"), spec("custom.step")];
const types = nodeTypeMap(specs);
const names = (list: NodeTypeSpec[]) => list.map((item) => item.type);

describe("layer links", () => {
  it("mirrors the server rules for layer pairs", () => {
    expect(layersLinkable("fe", "db")).toBe(false);
    expect(layersLinkable("db", "infra")).toBe(false);
    expect(layersLinkable("fe", "be")).toBe(true);
    expect(layersLinkable("db", "neutral")).toBe(true);
    expect(defaultVia("fe", "be")).toBe("http");
    expect(defaultVia("be", "db")).toBe("sql");
    expect(defaultVia("be", "be")).toBeUndefined();
  });
  it("narrows the palette to types allowed after (or before) the port", () => {
    expect(names(linkableTypes(specs, "fe", "out"))).toEqual(["fe.click", "be.function", "infra.api", "transform.set", "custom.step"]);
    expect(names(linkableTypes(specs, "db", "in"))).toEqual(["be.function", "db.write", "transform.set", "custom.step"]);
    expect(linkableTypes(specs, undefined, "out")).toHaveLength(specs.length);
  });
  it("puts the new node into its layer lane, joins the edge with via and gives a custom step the anchor layer", () => {
    const edge = { id: "form-x", source_node: "form", source_port: "main", target_node: "x", target_port: "main", kind: "main" as const };
    const form = { id: "form", type: "fe.click", position: { x: 0, y: 0 } };
    const custom = settleAdded({ nodes: [form, { id: "x", type: "custom.step", position: { x: 260, y: 0 } }], edges: [edge] }, types, "form");
    expect(custom.nodes.at(-1)!.layer).toBe("fe");
    expect(custom.edges[0].via).toBeUndefined();
    const placed = settleAdded({ nodes: [form, { id: "x", type: "be.function", position: { x: 260, y: 0 } }], edges: [edge] }, types, "form");
    expect(placed.nodes.at(-1)!.layer).toBeUndefined();
    expect(placed.nodes.at(-1)!.position!.y).toBe(116 + 70);
    expect(placed.edges[0].via).toBe("http");
    const mate = settleAdded({ nodes: [{ id: "a", type: "be.function", position: { x: 0, y: 300 } }, { id: "b", type: "be.function", position: { x: 260, y: 0 } }], edges: [] }, types, "a");
    expect(mate.nodes.at(-1)!.position!.y).toBe(300);
  });
});
