import { afterEach, describe, expect, it, vi } from "vitest";
import { positionChanges, saveCanvasGraph, withPositions, type PositionsResponse } from "@/editor/canvas/board/logic/graph-positions";
import type { CanvasNode, Graph, View } from "@/shared/types/logic/types";

const node = (id: string, x = 0, y = 0): CanvasNode => ({ id, parentId: null, kind: "node", name: id, purpose: "", x, y }) as CanvasNode;
const graph: Graph = { nodes: [node("a"), node("b", 300)], edges: [{ id: "e1", source: "a", target: "b" }] as Graph["edges"] };
const view = { graph, digest: "d1", readOnly: false, source: "", sha: null, branch: null, dirty: false, graphStatus: "present",
  workspaces: [], observedAt: "t0", architectureRevision: 0 } as View;
const moved = (id: string, x: number, y: number): Graph => ({ ...graph, nodes: graph.nodes.map((n) => (n.id === id ? { ...n, x, y } : n)) });

describe("graph positions", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("finds a pure move of existing nodes and rounds it like the server", () => {
    expect(positionChanges(graph, moved("b", 320.6, 19.4))).toEqual([{ id: "b", x: 321, y: 19 }]);
    const both = { ...graph, nodes: [node("a", 5, 5), node("b", 9, 9)] };
    expect(positionChanges(graph, both)).toEqual([{ id: "a", x: 5, y: 5 }, { id: "b", x: 9, y: 9 }]);
  });

  it("refuses anything that is not only a move", () => {
    expect(positionChanges(graph, graph)).toBeNull();
    expect(positionChanges(graph, { ...graph, nodes: [...graph.nodes, node("c")] })).toBeNull();
    expect(positionChanges(graph, { ...graph, nodes: [graph.nodes[1], graph.nodes[0]] })).toBeNull();
    expect(positionChanges(graph, { ...graph, nodes: [{ ...node("a", 1, 1), name: "jiný" }, graph.nodes[1]] })).toBeNull();
    expect(positionChanges(graph, { ...moved("a", 1, 1), edges: [] })).toBeNull();
    const offsets = { ...graph, nodes: [{ ...graph.nodes[0], blockOffsets: { p: { dx: 1, dy: 1 } } } as CanvasNode, graph.nodes[1]] };
    expect(positionChanges(graph, offsets)).toBeNull();
  });

  it("composes the saved view from the base graph and the server head", () => {
    const response = { ...view, digest: "d2", observedAt: "t1", architectureRevision: 1, positions: [{ id: "b", x: 321, y: 19 }] } as unknown as PositionsResponse;
    delete (response as Partial<View>).graph;
    const saved = withPositions(view, response);
    expect(saved.digest).toBe("d2");
    expect(saved.architectureRevision).toBe(1);
    expect(saved.graph.nodes.map((n) => [n.id, n.x, n.y])).toEqual([["a", 0, 0], ["b", 321, 19]]);
    expect(saved.graph.nodes[0]).toBe(graph.nodes[0]);
    expect(saved.graph.edges).toBe(graph.edges);
    expect(saved).not.toHaveProperty("positions");
  });

  it("sends a move to /api/graph/positions and everything else (incl. undo) as the full graph", async () => {
    const calls: { url: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body ?? "{}"));
      calls.push({ url, body });
      const answer = url === "/api/graph/positions" ? { ...view, graph: undefined, digest: "d2", positions: body.positions } : { ...view, graph: body.graph, digest: "d3" };
      return new Response(JSON.stringify(answer), { status: 200 });
    }));
    const request = { project: "p", workspace: "w", digest: "d1", undo: false };
    const slim = await saveCanvasGraph(view, { ...request, graph: moved("a", 40, 50) });
    expect(slim.digest).toBe("d2");
    expect(slim.graph.nodes[0]).toMatchObject({ x: 40, y: 50 });
    const full = await saveCanvasGraph(view, { ...request, graph: { ...graph, nodes: [...graph.nodes, node("c")] } });
    await saveCanvasGraph(view, { ...request, undo: true, graph: moved("a", 1, 1) });
    const writes = calls.filter((call) => call.url.startsWith("/api/graph"));
    expect(writes.map((call) => call.url)).toEqual(["/api/graph/positions", "/api/graph", "/api/graph"]);
    expect(writes[0].body).toEqual({ project: "p", workspace: "w", digest: "d1", positions: [{ id: "a", x: 40, y: 50 }] });
    expect(full.digest).toBe("d3");
  });
});
