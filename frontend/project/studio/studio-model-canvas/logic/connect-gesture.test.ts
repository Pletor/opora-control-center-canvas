import { describe, expect, it } from "vitest";
import { emptyStudioModel } from "../../model/logic/model-types";
import { addNode, type EditModel } from "../../studio-model/logic/model-edit";
import { orient, portClick, portKey, portTargets, type PendingPort } from "./connect-gesture";

const out: PendingPort = { nodeId: "c", portId: "http-out", direction: "output" };
const lbIn: PendingPort = { nodeId: "lb", portId: "http-in", direction: "input" };

describe("connect gesture", () => {
  it("selects, cancels, switches and links by clicks in either order", () => {
    expect(portClick(null, out)).toEqual({ pending: out });
    expect(portClick(out, out)).toEqual({ pending: null });
    const other: PendingPort = { nodeId: "lb", portId: "http-out", direction: "output" };
    expect(portClick(out, other)).toEqual({ pending: other });
    const link = { from: { nodeId: "c", portId: "http-out" }, to: { nodeId: "lb", portId: "http-in" } };
    expect(portClick(out, lbIn)).toEqual({ pending: null, link });
    expect(portClick(lbIn, out)).toEqual({ pending: null, link });
    expect(orient(out, out)).toBeNull();
  });

  it("marks opposite ports compatible or invalid by the model rules", () => {
    let model: EditModel = emptyStudioModel("web");
    for (const [type, id] of [["client", "c"], ["load-balancer", "lb"], ["postgresql", "db"]]) model = addNode(model, type, undefined, id).model;
    const targets = portTargets(model, out);
    expect(targets.get(portKey({ nodeId: "lb", portId: "http-in" }))).toBe("compatible");
    expect(targets.get(portKey({ nodeId: "lb", portId: "health-in" }))).toBe("invalid");
    expect(targets.get(portKey({ nodeId: "db", portId: "sql-in" }))).toBe("invalid");
    expect(targets.has(portKey({ nodeId: "lb", portId: "http-out" }))).toBe(false);
    expect(portTargets(model, null).size).toBe(0);
  });
});
