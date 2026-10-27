import { describe, expect, it } from "vitest";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import { cardFace, cardPorts, portFlow } from "./card-face";

const node = (extra: Partial<CanvasNode> = {}): CanvasNode => ({ id: "n", parentId: "home", name: "n", purpose: "", kind: "node", x: 0, y: 0, ...extra });
const edges: GraphEdge[] = [
  { id: "1", source: "a", target: "n", carries: "data" }, { id: "2", source: "b", target: "n", carries: "event" }, { id: "3", source: "c", target: "n", carries: "event" },
  { id: "4", source: "n", target: "d" }, { id: "5", source: "n", target: "e", port: "rule" },
];

describe("map card face", () => {
  it("colours a port by the dominant carries of its links", () => {
    expect(portFlow(edges, "n", "in")).toBe("event");
    expect(portFlow(edges, "n", "out")).toBe("unspecified");
    expect(cardPorts(edges, "d")).toEqual({ in: "unspecified", out: null });
    expect(cardPorts([], "n")).toEqual({ in: null, out: null });
  });

  it("names the kind and the address under the head", () => {
    expect(cardFace(node({ site: { kind: "page", path: "/pay" } }))).toEqual({ kind: "Podstránka", subtitle: "/pay" });
    expect(cardFace(node({ kind: "sector" }))).toEqual({ kind: "Sektor", subtitle: "" });
    expect(cardFace(node({ card: { tech: "React" } }))).toEqual({ kind: "Uzel", subtitle: "React" });
  });
});
