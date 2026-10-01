import { describe, expect, it } from "vitest";
import { hasChildren, prunedCollapsed, subtreeSize, visibleIndexes } from "@/editor/node-detail/content/logic/block-tree";
import type { Block } from "@/editor/node-detail/content/logic/block-commands";

function tree(...depths: number[]): Block[] {
  return depths.map((depth, i) => ({ id: "b" + i, depth, text: "blok " + i }));
}

describe("strom osnovy", () => {
  it("podstrom sahá po první blok, který se vynoří zpátky", () => {
    const blocks = tree(0, 1, 2, 1, 0);
    expect(subtreeSize(blocks, 0)).toBe(3);
    expect(subtreeSize(blocks, 1)).toBe(1);
    expect(subtreeSize(blocks, 2)).toBe(0);
    expect(subtreeSize(blocks, 4)).toBe(0);
  });

  it("děti pozná jen ten, kdo je má", () => {
    const blocks = tree(0, 1, 0);
    expect(hasChildren(blocks, 0)).toBe(true);
    expect(hasChildren(blocks, 1)).toBe(false);
    expect(hasChildren(blocks, 2)).toBe(false);
  });

  it("sbalený rodič skryje celý podstrom, ne jen první dítě", () => {
    const blocks = tree(0, 1, 2, 1, 0);
    expect(visibleIndexes(blocks, new Set(["b0"]))).toEqual([0, 4]);
    expect(visibleIndexes(blocks, new Set(["b1"]))).toEqual([0, 1, 3, 4]);
  });

  it("bez sbalení jsou vidět všechny bloky", () => {
    const blocks = tree(0, 1, 1);
    expect(visibleIndexes(blocks, new Set())).toEqual([0, 1, 2]);
  });

  it("sbalení bezdětného bloku se zahodí, sbalení rodiče zůstane", () => {
    const blocks = tree(0, 1, 0);
    expect([...prunedCollapsed(blocks, new Set(["b0", "b2", "zmizelý"]))]).toEqual(["b0"]);
  });
});
