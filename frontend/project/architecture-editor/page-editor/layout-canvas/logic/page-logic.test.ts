import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { pageLogic } from "./page-logic";

const node = (id: string, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId: "p", kind: "node", name: id, purpose: "", x: 0, y: 0, ...extra });
const graph: Graph = { edges: [], nodes: [
  { ...node("p"), parentId: "d", site: { kind: "page", path: "/" } },
  node("buy", { element: { kind: "action" }, card: { section: "cta" } }),
  node("member", { element: { kind: "actor" } }),
  node("lost", { element: { kind: "service" }, card: { section: "gone" } }),
  node("old"), node("sector", { kind: "sector" }),
  node("sub", { site: { kind: "page", path: "/sub" } }),
] };

describe("prvky logiky podle boxů", () => {
  it("prvek s boxem jde do boxu, bez boxu nebo se ztraceným boxem na celou stránku, starší karty se spočítají", () => {
    const logic = pageLogic(graph, "p", new Set(["cta"]));
    expect(logic.byBox.get("cta")?.map((item) => item.id)).toEqual(["buy"]);
    expect(logic.whole.map((item) => item.id)).toEqual(["member", "lost"]);
    expect(logic.legacy).toBe(2);
  });
});
