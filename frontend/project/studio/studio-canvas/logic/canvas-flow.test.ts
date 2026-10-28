import { describe, expect, it } from "vitest";
import type { StudioCardView } from "../../studio-card/logic/card-view";
import { flowEdges, flowNodes, linkTitle } from "./canvas-flow";
import { layoutLevel } from "./studio-layout";

const view = (id: string): StudioCardView => ({ id, name: id, kind: "component", kindLabel: "Komponenta", subtitle: "", purpose: "", icon: "box", state: "plan", stateLabel: "plán", summary: "bez dětí", holes: 0, children: 0, modelTarget: false, guards: null });

describe("canvas flow", () => {
  it("makes read-only card nodes on layout positions and a group frame behind them", () => {
    const layout = layoutLevel([{ id: "a" }, { id: "b", grouped: true }], []);
    const nodes = flowNodes([view("a"), view("b")], layout, "b", (card) => ({ view: card }));
    expect(nodes.map((node) => [node.id, node.type, node.selected ?? false])).toEqual([["studio-group-unsectioned", "studio-group", false], ["a", "studio-card", false], ["b", "studio-card", true]]);
    expect(nodes[0]).toMatchObject({ data: { label: "Bez sekce" }, selectable: false, zIndex: -1 });
    expect(nodes[1]).toMatchObject({ draggable: false, connectable: false, position: { x: 0, y: 0 } });
  });

  it("turns summary links into studio-link edges with a title naming flow and count", () => {
    const edges = flowEdges([{ id: "a->b", source: "a", target: "b", count: 3, carries: "data", kinds: { data: 2, event: 1 }, edgeIds: ["1", "2", "3"] }]);
    expect(edges).toEqual([{ id: "a->b", source: "a", target: "b", type: "studio-link", focusable: false, selectable: false, data: { count: 3, carries: "data", title: "Data · 3 vazby (Data 2, Událost 1)" } }]);
    expect(linkTitle({ count: 1, carries: "unspecified", kinds: { unspecified: 1 } })).toBe("Neurčeno · 1 vazba");
    expect(linkTitle({ count: 7, carries: "command", kinds: { command: 7 } })).toBe("Příkaz · 7 vazeb");
  });
});
