import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import { buildTower } from "./tower-model";
import { collapseChain, defaultOpen, layerChildren, openKey, readOpen, rootLayer, writeOpen } from "./tower-view";

const node = (id: string, kind: CanvasNode["kind"], parentId: string | null, x = 0, y = 0, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, kind, parentId, name: id.toUpperCase(), purpose: "", x, y, ...extra });
const tower = (nodes: CanvasNode[]) => buildTower({ graph: { nodes, edges: [] } as Graph, state: emptyDesktopState() });

describe("collapseChain – průchozí řetěz", () => {
  it("řetěz tří kontejnerů skončí tam, kde se vrstva větví", () => {
    const t = tower([
      node("al", "sector", null), node("pr", "node", "al"), node("tr", "node", "pr"),
      node("v1", "sector", "tr", 0, 0), node("v2", "sector", "tr", 400, 0), node("k", "node", "v1"),
    ]);
    const collapsed = collapseChain(rootLayer(t));
    expect(collapsed.chain).toEqual([{ id: "al", name: "AL" }, { id: "pr", name: "PR" }, { id: "tr", name: "TR" }]);
    expect(collapsed.layer.sectors.map((s) => s.id)).toEqual(["v1", "v2"]);
    expect(layerChildren(collapsed.layer)).toBe(2);
  });

  it("karta navíc řetěz přeruší", () => {
    const t = tower([
      node("al", "sector", null), node("pr", "node", "al"), node("extra", "node", "al", 500, 0),
      node("tr", "node", "pr"), node("v1", "sector", "tr"),
    ]);
    const collapsed = collapseChain(rootLayer(t));
    expect(collapsed.chain.map((c) => c.id)).toEqual(["al"]);
    expect(collapsed.layer.containers.map((c) => c.id)).toEqual(["pr"]);
    expect(collapsed.layer.cards.map((c) => c.id)).toEqual(["extra"]);
  });

  it("bez řetězu vrstvu vrátí beze změny; oblast na kořeni řetěz nespustí", () => {
    const branching = rootLayer(tower([node("a", "sector", null), node("b", "sector", null, 500, 0)]));
    expect(collapseChain(branching)).toEqual({ chain: [], layer: branching });
    const withArea = rootLayer(tower([node("ar", "area", null, 0, 0, { size: { w: 1000, h: 1000 } }), node("s", "sector", null, 10, 10)]));
    expect(collapseChain(withArea).chain).toEqual([]);
    const lonelyCard = rootLayer(tower([node("c", "node", null)]));
    expect(collapseChain(lonelyCard).chain).toEqual([]);
  });
});

describe("výchozí rozbalení a paměť", () => {
  it("rozbalená je jen první úroveň větvení", () => {
    expect(defaultOpen(1, 2)).toBe(true);
    expect(defaultOpen(1, 1)).toBe(false);
    expect(defaultOpen(2, 5)).toBe(false);
  });

  it("čte a zapisuje per projekt a přežije poškozený zápis i chybu úložiště", () => {
    const data = new Map<string, string>();
    const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    writeOpen(storage, "p1", { a: true, b: false });
    expect(data.has(openKey("p1"))).toBe(true);
    expect(readOpen(storage, "p1")).toEqual({ a: true, b: false });
    expect(readOpen(storage, "p2")).toEqual({});
    data.set(openKey("p3"), "{nejde");
    expect(readOpen(storage, "p3")).toEqual({});
    data.set(openKey("p4"), JSON.stringify({ a: true, b: "ano" }));
    expect(readOpen(storage, "p4")).toEqual({ a: true });
    const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("full"); } };
    expect(readOpen(broken, "p1")).toEqual({});
    expect(() => writeOpen(broken, "p1", {})).not.toThrow();
    expect(readOpen(undefined, "p1")).toEqual({});
  });
});
