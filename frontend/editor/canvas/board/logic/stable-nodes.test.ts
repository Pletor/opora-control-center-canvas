import { describe, expect, it } from "vitest";
import type { Node } from "@xyflow/react";
import type { Graph } from "@/shared/types/logic/types";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";
import { buildBoardIndex } from "./board-index";
import { buildLayerNodes, CULL_FROM, CULL_VISIBLE, shouldCull, type LayerInput } from "./layer-nodes";
import { changedNodes, reuseNodes, sameShell, sameValue } from "./stable-nodes";
import { indexVault } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

/** Vrstva s `cards` kartami po třech blocích se dvěma porty, pár sektory, komentář a oblast. */
function board(cards = 300): { graph: Graph; state: DesktopState } {
  const graph: Graph = { nodes: [], edges: [] };
  const state = emptyDesktopState();
  for (let i = 0; i < cards; i++) {
    const id = "n-" + i;
    const kind = i === 1 ? "comment" : i === 2 ? "area" : i % 50 === 0 ? "sector" : "node";
    graph.nodes.push({ id, parentId: null, kind, name: "Karta " + i, purpose: "", x: (i % 30) * 320, y: Math.floor(i / 30) * 260,
      size: kind === "area" ? { w: 900, h: 600 } : undefined, sourceRef: i % 9 === 0 ? { origin: "planned", path: "frontend/x.ts", kind: "file" } : undefined });
    state.nodes[id] = { phase: "build", criteria: [], steps: [], rules: [],
      blocks: [0, 1, 2].map((b) => ({ id: `${id}-b${b}`, number: String(b + 1), title: "Blok " + b, text: "Text " + b, tags: [], todos: [], images: [],
        parentBlockId: "", state: { status: "open" as const, condition: "", onMet: { kind: "none" as const, targetId: "", note: "" }, onUnmet: { kind: "none" as const, targetId: "", note: "" } },
        ports: [{ id: "p1", label: "Ano" }, { id: "p2", label: "Ne" }] })),
      done: i % 5 === 0 ? { confirmed: false, at: "", by: "agent", note: "návrh" } : undefined };
    if (i > 3) graph.edges.push({ id: "e" + i, source: "n-" + (i - 1), target: id, port: "next" });
  }
  return { graph, state };
}

function inputFor(graph: Graph, state: DesktopState, patch: Partial<LayerInput> = {}): LayerInput {
  const index = buildBoardIndex(graph, state);
  return { graph, state, index, parent: null, selected: null, multiSelected: new Set(), selectedBlock: null, editing: null, disabled: false,
    openBlocks: {}, tagFilter: "", moved: new Set(), vaultIndex: indexVault([]),
    sourceContext: { project: "p", workspace: "w" }, can: { realize: true, rules: true },
    ...patch };
}

/** Jako React Flow po prvním vykreslení: každý uzel má změřený rozměr. */
const measure = (nodes: Node[]) => nodes.map((node) => ({ ...node, measured: { width: 360, height: 300 }, width: 360, height: 300 }));

const hasFunction = (value: unknown): boolean =>
  typeof value === "function" || (!!value && typeof value === "object" && Object.values(value as object).some(hasFunction));

describe("stable layer nodes", () => {
  const { graph, state } = board(300);
  const first = measure(buildLayerNodes(inputFor(graph, state)));

  it("builds card data without a single function, so it can be compared", () => {
    expect(first).toHaveLength(300);
    expect(first.some((node) => hasFunction(node.data))).toBe(false);
  });

  it("selecting one card on a 300-card board re-renders at most 3 cards", () => {
    const pickA = reuseNodes(first, buildLayerNodes(inputFor(graph, state, { selected: "n-10" })));
    expect(changedNodes(first, pickA)).toEqual(["n-10"]);
    const pickB = reuseNodes(pickA, buildLayerNodes(inputFor(graph, state, { selected: "n-11", selectedBlock: "n-11-b0" })));
    const changed = changedNodes(pickA, pickB);
    expect(changed.sort()).toEqual(["n-10", "n-11"]);
    expect(changed.length).toBeLessThanOrEqual(3);
  });

  it("an idle poll with equal data (new objects) re-renders no card", () => {
    const rows = Object.fromEntries(graph.nodes.map((n) => [n.id, { id: n.id, name: n.name, status: "frontier" as const }]));
    const polled = reuseNodes(first, buildLayerNodes(inputFor(graph, state, { frontier: rows })));
    const again = reuseNodes(polled, buildLayerNodes(inputFor(graph, state, { frontier: JSON.parse(JSON.stringify(rows)) })));
    expect(changedNodes(polled, again)).toEqual([]);
  });

  it("an edit of one block re-renders only that card", () => {
    const edited: DesktopState = { ...state, nodes: { ...state.nodes, "n-20": { ...state.nodes["n-20"],
      blocks: state.nodes["n-20"].blocks!.map((b, i) => i === 0 ? { ...b, text: "nový text" } : b) } } };
    const next = reuseNodes(first, buildLayerNodes(inputFor(graph, edited)));
    expect(changedNodes(first, next)).toEqual(["n-20"]);
  });

  it("a new agent-state snapshot re-renders only cards whose face changed", () => {
    const card = (nodeId: string, reason: string) => ({ nodeId, stage: "plan" as const, health: "ok" as const, reason, executionId: null });
    const agent = (reason: string) => ({ cards: new Map([["n-30", card("n-30", reason)], ["n-31", card("n-31", "card_in_plan")]]), decisions: [] });
    const before = reuseNodes(first, buildLayerNodes(inputFor(graph, state, { agent: agent("card_in_plan") })));
    const after = reuseNodes(before, buildLayerNodes(inputFor(graph, state, { agent: agent("card_closed") })));
    expect(changedNodes(before, after)).toEqual(["n-30"]);
  });

  it("keeps measured on reused nodes and carries it over to rebuilt nodes (inputs keep focus)", () => {
    const next = reuseNodes(first, buildLayerNodes(inputFor(graph, state, { selected: "n-30" })));
    const rebuilt = next.find((n) => n.id === "n-30")!;
    expect(rebuilt).not.toBe(first.find((n) => n.id === "n-30"));
    expect(rebuilt.measured).toEqual({ width: 360, height: 300 });
    expect([rebuilt.width, rebuilt.height]).toEqual([360, 300]);
    expect(next.find((n) => n.id === "n-31")).toBe(first.find((n) => n.id === "n-31"));
  });

  it("does not reuse a node moved by drag (position differs from the graph)", () => {
    const dragged = first.map((n) => n.id === "n-40" ? { ...n, position: { x: 1, y: 1 } } : n);
    const next = reuseNodes(dragged, buildLayerNodes(inputFor(graph, state)));
    expect(changedNodes(dragged, next)).toEqual(["n-40"]);
    expect(next.find((n) => n.id === "n-40")!.measured).toBeDefined();
  });

  it("culls only large layers now that drafts live in a store", () => {
    expect(CULL_VISIBLE).toBe(true);
    expect(shouldCull(CULL_FROM * 10)).toBe(true);
    expect(shouldCull(CULL_FROM)).toBe(true);
    expect(shouldCull(CULL_FROM - 1)).toBe(false);
    expect(shouldCull(20)).toBe(false);
  });
});

describe("sameShell and reuse", () => {
  const card = (patch: Partial<Node> = {}): Node => ({ id: "a", type: "canvas", position: { x: 0, y: 0 }, selected: false, data: { v: 1 }, ...patch });

  it("compares every shell prop the builder sets, not just a fixed list", () => {
    expect(sameShell(card(), card())).toBe(true);
    for (const patch of [{ parentId: "p" }, { extent: "parent" as const }, { draggable: false }, { selectable: false }, { hidden: true },
      { zIndex: 2 }, { className: "x" }, { style: { width: 1 } }, { type: "area" }, { connectable: false }, { position: { x: 1, y: 0 } }])
      expect(sameShell(card(), card(patch))).toBe(false);
    expect(sameShell(card({ style: { width: 4 } }), card({ style: { width: 4 } }))).toBe(true);
    expect(sameShell(card({ data: { v: 1 } }), card({ data: { v: 2 } }))).toBe(false);
  });

  it("ignores measurements React Flow wrote, but not explicit new dimensions", () => {
    const measured = card({ measured: { width: 300, height: 200 }, width: 300, height: 200 });
    expect(sameShell(measured, card())).toBe(true);
    expect(sameShell(measured, card({ width: 500 }))).toBe(false);
  });

  it("lets explicit width/height of the new node win over carried measurements", () => {
    const old = card({ measured: { width: 300, height: 200 }, width: 300, height: 200, data: { v: 1 } });
    const [next] = reuseNodes([old], [card({ data: { v: 2 }, width: 720, height: 480 })]);
    expect([next.width, next.height]).toEqual([720, 480]);
    expect(next.measured).toEqual({ width: 300, height: 200 });
    const [plain] = reuseNodes([old], [card({ data: { v: 2 } })]);
    expect([plain.width, plain.height]).toEqual([300, 200]);
  });

  it("carries measurements only to a node of the same type", () => {
    const old = card({ measured: { width: 300, height: 200 } });
    const [next] = reuseNodes([old], [card({ type: "comment" })]);
    expect(next.measured).toBeUndefined();
  });

  it("rebuilds once a node React Flow marked (dragging) and reuses it afterwards", () => {
    const marked = { ...card(), dragging: false } as Node;
    const [rebuilt] = reuseNodes([marked], [card()]);
    expect(rebuilt).not.toBe(marked);
    const [again] = reuseNodes([rebuilt], [card()]);
    expect(again).toBe(rebuilt);
  });
});

describe("sameValue", () => {
  it("compares plain data deeply and functions by reference", () => {
    const f = () => {};
    expect(sameValue({ a: [1, { b: "x" }], c: undefined }, { a: [1, { b: "x" }], c: undefined })).toBe(true);
    expect(sameValue({ a: 1 }, { a: 1, b: undefined })).toBe(false);
    expect(sameValue([1, 2], [1, 2, 3])).toBe(false);
    expect(sameValue({ f }, { f })).toBe(true);
    expect(sameValue({ f }, { f: () => {} })).toBe(false);
    expect(sameValue(new Map(), new Map())).toBe(false);
  });
});
