import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { ancestorIds, appendSkeleton, STARTER_SECTORS, structureNodes } from "./skeleton";

describe("Kostra a sdílený návrhový graf", () => {
  let sequence = 0;
  const id = () => `part-${++sequence}`;
  it("doplní chybějící sektory bez duplikace při opakování a zachová existující vazby i metadata", () => {
    const original: Graph = { nodes: [{ id: "existing", parentId: null, kind: "sector", name: "Frontend", purpose: "Původní účel", x: 13, y: 27, sourceRef: { origin: "existing", path: "frontend", kind: "directory" } }], edges: [] };
    const next = appendSkeleton(original, null, STARTER_SECTORS.slice(0, 3), "sector", id);
    expect(next.nodes).toHaveLength(3);
    expect(next.nodes[0]).toBe(original.nodes[0]);
    expect(next.edges).toBe(original.edges);
    expect(appendSkeleton(next, null, STARTER_SECTORS.slice(0, 3), "sector", id)).toBe(next);
    expect(original.nodes).toHaveLength(1);
    expect(next.nodes.slice(1).every((node) => node.sourceRef === undefined)).toBe(true);
  });
  it("vnořuje libovolné části pod stejné identity a otevře celou cestu", () => {
    let graph = appendSkeleton({ nodes: [], edges: [] }, null, ["Frontend"], "sector", id);
    const root = graph.nodes[0].id;
    graph = appendSkeleton(graph, root, ["Objednávky"], "node", id);
    const domain = graph.nodes[1].id;
    graph = appendSkeleton(graph, domain, ["Detail"], "node", id);
    const detail = graph.nodes[2].id;
    graph = appendSkeleton(graph, detail, ["Cena"], "node", id);
    expect(ancestorIds(graph.nodes, graph.nodes[3].id)).toEqual([detail, domain, root]);
    expect(graph.nodes[3].parentId).toBe(detail);
  });
  it("odmítá cizího rodiče a nepoužije komentář jako komponentu", () => {
    const note: CanvasNode = { id: "note", parentId: null, kind: "comment", name: "Poznámka", purpose: "", x: 0, y: 0 };
    const graph = { nodes: [note], edges: [] };
    expect(() => appendSkeleton(graph, "missing", ["Část"], "node", id)).toThrow();
    expect(() => appendSkeleton(graph, "note", ["Část"], "node", id)).toThrow();
    expect(structureNodes(graph.nodes)).toEqual([]);
  });
});
