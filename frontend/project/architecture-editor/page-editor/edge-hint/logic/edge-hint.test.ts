import { describe, expect, it } from "vitest";
import type { Graph, GraphEdge } from "@/shared/types/logic/types";
import { edgeHintText } from "./edge-hint";

const node = (id: string, name: string) => ({ id, name, kind: "node", parentId: null, x: 0, y: 0 });
const graph = { nodes: [node("a", "Přihlášení"), node("b", "Dashboard")], edges: [] } as unknown as Graph;
const edge = (extra: Partial<GraphEdge> = {}): GraphEdge => ({ id: "e", source: "a", target: "b", ...extra });

describe("edgeHintText", () => {
  it("names the carried kind in Czech and the route by node names", () => {
    expect(edgeHintText(edge({ carries: "data" }), graph)).toEqual({ kind: "Data", route: "Přihlášení → Dashboard" });
  });
  it("tells where to set an undetermined kind", () => {
    expect(edgeHintText(edge(), graph).kind).toBe("Neurčeno – nastavte v Detailu prvku → Vazby");
  });
  it("does not ask for a kind on edges that cannot carry one", () => {
    expect(edgeHintText(edge({ port: "flow" }), graph).kind).toBe("Druh toku se u této vazby nenastavuje");
  });
  it("falls back to the id of a missing node", () => {
    expect(edgeHintText(edge({ target: "gone" }), graph).route).toBe("Přihlášení → gone");
  });
});
