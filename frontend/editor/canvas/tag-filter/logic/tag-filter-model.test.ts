import { describe, expect, it } from "vitest";
import { tagCounts } from "./tag-filter-model";
import { emptyBranch, emptyDesktopState, type Block, type DesktopState } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";

function block(id: string, tags: string[]): Block {
  return { id, number: id, title: id, text: "", tags, todos: [], images: [], parentBlockId: "",
    state: { status: "open", condition: "", onMet: emptyBranch(), onUnmet: emptyBranch() } };
}

const graph: Graph = {
  nodes: [
    { id: "a", parentId: null, kind: "node", name: "A", purpose: "", x: 0, y: 0 },
    { id: "b", parentId: null, kind: "node", name: "B", purpose: "", x: 0, y: 0 },
    { id: "c", parentId: "a", kind: "node", name: "C", purpose: "", x: 0, y: 0 },
    { id: "area-1", parentId: null, kind: "area", name: "Oblast", purpose: "", x: 0, y: 0, size: { w: 200, h: 200 } },
  ],
  edges: [],
};

describe("tag-filter-model", () => {
  it("počítá karty ve vrstvě podle štítku, seřazené podle četnosti a jména", () => {
    const state: DesktopState = { ...emptyDesktopState(), nodes: {
      a: { phase: "discover", criteria: [], steps: [], blocks: [block("1", ["ui", "auth"]), block("2", ["ui"])] },
      b: { phase: "discover", criteria: [], steps: [], blocks: [block("1", ["auth"])] },
      c: { phase: "discover", criteria: [], steps: [], blocks: [block("1", ["hluboko"])] },
      "area-1": { phase: "discover", criteria: [], steps: [], blocks: [block("1", ["by-se-nemelo-pocitat"])] },
    } };
    expect(tagCounts(graph, null, state)).toEqual([{ tag: "auth", count: 2 }, { tag: "ui", count: 1 }]);
    expect(tagCounts(graph, "a", state)).toEqual([{ tag: "hluboko", count: 1 }]);
    expect(tagCounts(graph, null, emptyDesktopState())).toEqual([]);
  });

  it("oblast se do počtu štítků nepočítá, i kdyby měla svoje bloky se štítky", () => {
    const state: DesktopState = { ...emptyDesktopState(), nodes: {
      "area-1": { phase: "discover", criteria: [], steps: [], blocks: [block("1", ["tok"])] },
    } };
    expect(tagCounts(graph, null, state)).toEqual([]);
  });
});
