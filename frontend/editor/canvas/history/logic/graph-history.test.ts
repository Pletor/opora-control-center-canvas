import { describe, expect, it } from "vitest";
import {
  emptyHistory,
  HISTORY_LIMIT,
  record,
  recordRemoval,
  redo,
  sameGraph,
  undo,
} from "./graph-history";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";

function node(id: string, x = 0, y = 0): CanvasNode {
  return { id, parentId: null, kind: "node", name: id, purpose: "", x, y };
}

function graph(...nodes: CanvasNode[]): Graph {
  return { nodes, edges: [] };
}

describe("graph-history", () => {
  it("prázdná historie nemá kam krokovat", () => {
    const history = emptyHistory();
    expect(history).toEqual({ past: [], future: [] });
    expect(undo(history, graph(node("a")))).toBeNull();
    expect(redo(history, graph(node("a")))).toBeNull();
  });

  it("sameGraph porovnává tvar, ne identitu", () => {
    expect(sameGraph(graph(node("a")), graph(node("a")))).toBe(true);
    expect(sameGraph(graph(node("a")), graph(node("a", 10)))).toBe(false);
    expect(sameGraph(graph(node("a")), graph(node("a"), node("b")))).toBe(false);
  });

  it("record odloží graf před změnou a nesáhne na původní historii", () => {
    const before = emptyHistory();
    const first = graph(node("a"));
    const after = record(before, first);
    expect(after.past).toEqual([{ graph: first }]);
    expect(before.past).toEqual([]);
  });

  it("record po kroku zpět zahodí větev dopředu", () => {
    const a = graph(node("a"));
    const b = graph(node("a", 10));
    const stepped = undo(record(emptyHistory(), a), b)!;
    expect(stepped.history.future).toEqual([b]);
    const branched = record(stepped.history, graph(node("a", 20)));
    expect(branched.future).toEqual([]);
  });

  it("record dvakrát po sobě týž graf nezaloží dva kroky", () => {
    const a = graph(node("a"));
    const once = record(emptyHistory(), a);
    const twice = record(once, graph(node("a")));
    expect(twice.past).toHaveLength(1);
    expect(twice).toBe(once);
  });

  it("record drží nejvýš HISTORY_LIMIT kroků a zahazuje nejstarší", () => {
    let history = emptyHistory();
    for (let i = 0; i <= HISTORY_LIMIT + 4; i++) history = record(history, graph(node("a", i)));
    expect(history.past).toHaveLength(HISTORY_LIMIT);
    expect(history.past[0]).toEqual({ graph: graph(node("a", 5)) });
    expect(history.past[HISTORY_LIMIT - 1]).toEqual({ graph: graph(node("a", HISTORY_LIMIT + 4)) });
  });

  it("krok zpět vrátí poslední snímek a aktuální graf odloží dopředu", () => {
    const a = graph(node("a"));
    const b = graph(node("a", 10));
    const stepped = undo(record(emptyHistory(), a), b)!;
    expect(stepped.graph).toEqual(a);
    expect(stepped.restore).toBeUndefined();
    expect(stepped.history.past).toEqual([]);
    expect(stepped.history.future).toEqual([b]);
  });

  it("krok vpřed je zrcadlo kroku zpět", () => {
    const a = graph(node("a"));
    const b = graph(node("a", 10));
    const back = undo(record(emptyHistory(), a), b)!;
    const forward = redo(back.history, back.graph)!;
    expect(forward.graph).toEqual(b);
    expect(forward.history.past).toEqual([{ graph: a }]);
    expect(forward.history.future).toEqual([]);
  });

  it("tři změny se vracejí po jedné a stejnou cestou zpátky", () => {
    const a = graph(node("a"));
    const b = graph(node("a", 10));
    const c = graph(node("a", 20));
    let history = record(record(emptyHistory(), a), b);
    const first = undo(history, c)!;
    expect(first.graph).toEqual(b);
    const second = undo(first.history, first.graph)!;
    expect(second.graph).toEqual(a);
    expect(undo(second.history, second.graph)).toBeNull();
    const forward = redo(second.history, second.graph)!;
    expect(forward.graph).toEqual(b);
    expect(redo(forward.history, forward.graph)!.graph).toEqual(c);
  });

  it("recordRemoval založí krok s obnovou a zahodí větev dopředu", () => {
    const a = graph(node("a"), node("b"));
    const b = graph(node("a"));
    const stepped = undo(record(emptyHistory(), a), b)!;
    const removed = recordRemoval(stepped.history, a, "rec-1");
    expect(removed.past).toEqual([{ graph: a, restore: "rec-1" }]);
    expect(removed.future).toEqual([]);
    expect(stepped.history.past).toEqual([]);
  });

  it("recordRemoval se nespojí s obyčejným krokem téhož grafu", () => {
    const a = graph(node("a"), node("b"));
    const removed = recordRemoval(record(emptyHistory(), a), a, "rec-1");
    expect(removed.past).toHaveLength(2);
    expect(record(removed, a).past).toHaveLength(3);
  });

  it("krok zpět na smazání vrací restore, krok vpřed za ním je obyčejný snímek", () => {
    const before = graph(node("a"), node("b"));
    const after = graph(node("a"));
    const back = undo(recordRemoval(emptyHistory(), before, "rec-1"), after)!;
    expect(back.restore).toBe("rec-1");
    expect(back.graph).toEqual(before);
    expect(back.history.future).toEqual([after]);
    const forward = redo(back.history, before)!;
    expect(forward.graph).toEqual(after);
    expect(forward.history.past).toEqual([{ graph: before }]);
    expect(undo(forward.history, after)!.restore).toBeUndefined();
  });
});
