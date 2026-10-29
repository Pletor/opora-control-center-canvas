import { describe, expect, it } from "vitest";
import type { LiveWorktree } from "./live-model";
import { tabStop, treeKey, visibleItems } from "./tree-nav";

const wt = (id: string, cards: string[] = [], sessions: string[] = []): LiveWorktree => ({
  id, branch: "work/" + id, actor: "a", state: "none", reasons: [],
  cards: cards.map((nodeId) => ({ nodeId, name: nodeId })),
  sessions: sessions.map((sid) => ({ source: "lease", id: sid, state: "active", nodeId: null, lastSeenAt: null })),
});
const trees = [wt("a", ["c1"], ["s1"]), wt("b")];

describe("klávesnice ve stromu worktree", () => {
  it("viditelné položky: rozbalený worktree ukáže relace a karty", () => {
    expect(visibleItems(trees, new Set()).map((item) => item.key)).toEqual(["w:a", "w:b"]);
    expect(visibleItems(trees, new Set(["a"])).map((item) => item.key)).toEqual(["w:a", "s:a:lease:s1", "c:a:c1", "w:b"]);
  });
  it("v pořadí Tab je jedna položka: zaměřená, jinak první", () => {
    const items = visibleItems(trees, new Set());
    expect(tabStop(items, "w:b")).toBe("w:b");
    expect(tabStop(items, "c:a:c1")).toBe("w:a");
    expect(tabStop([], null)).toBeNull();
  });
  it("šipky, Home a End", () => {
    const open = new Set(["a"]);
    const items = visibleItems(trees, open);
    expect(treeKey(items, "w:a", "ArrowDown", open)).toEqual({ focus: "s:a:lease:s1" });
    expect(treeKey(items, "w:b", "ArrowDown", open)).toEqual({ focus: "w:b" });
    expect(treeKey(items, "w:a", "ArrowUp", open)).toEqual({ focus: "w:a" });
    expect(treeKey(items, "c:a:c1", "Home", open)).toEqual({ focus: "w:a" });
    expect(treeKey(items, "w:a", "End", open)).toEqual({ focus: "w:b" });
  });
  it("vpravo rozbalí nebo jde na první dítě, vlevo sbalí nebo vrátí na rodiče", () => {
    const closed = new Set<string>();
    expect(treeKey(visibleItems(trees, closed), "w:a", "ArrowRight", closed)).toEqual({ expand: "a" });
    const open = new Set(["a"]);
    const items = visibleItems(trees, open);
    expect(treeKey(items, "w:a", "ArrowRight", open)).toEqual({ focus: "s:a:lease:s1" });
    expect(treeKey(items, "c:a:c1", "ArrowLeft", open)).toEqual({ focus: "w:a" });
    expect(treeKey(items, "w:a", "ArrowLeft", open)).toEqual({ collapse: "a" });
    expect(treeKey(items, "w:b", "ArrowLeft", open)).toEqual({});
  });
  it("Enter a mezera položku použijí, jiné klávesy stromu nepatří", () => {
    const open = new Set(["a"]);
    const items = visibleItems(trees, open);
    expect(treeKey(items, "c:a:c1", "Enter", open)?.activate).toMatchObject({ kind: "card", worktreeId: "a", targetId: "c1" });
    expect(treeKey(items, "w:b", " ", open)?.activate).toMatchObject({ kind: "worktree" });
    expect(treeKey(items, "w:b", "x", open)).toBeNull();
    expect(treeKey(items, "chybí", "ArrowDown", open)).toBeNull();
  });
});
