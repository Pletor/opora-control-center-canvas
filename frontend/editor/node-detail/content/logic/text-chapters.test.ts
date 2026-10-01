import { describe, expect, it } from "vitest";
import {
  EMPTY_CHAPTER_VIEW, collapseAll, expandAll, expandedCount, toggleChapter, viewWithExpanded, withMounted,
} from "./text-chapters";

const sorted = (set: ReadonlySet<string>) => [...set].sort();

describe("text-chapters", () => {
  it("výchozí pohled je vše sbalené a nic připojené", () => {
    expect(EMPTY_CHAPTER_VIEW.expanded.size).toBe(0);
    expect(EMPTY_CHAPTER_VIEW.mounted.size).toBe(0);
  });

  it("toggleChapter přidá a odebere id a vstup nemění", () => {
    const start: ReadonlySet<string> = new Set(["a"]);
    const added = toggleChapter(start, "b");
    expect(sorted(added)).toEqual(["a", "b"]);
    expect(sorted(toggleChapter(added, "a"))).toEqual(["b"]);
    expect(sorted(start)).toEqual(["a"]);
    expect(added).not.toBe(start);
  });

  it("expandAll rozbalí přesně daná id, collapseAll nic", () => {
    expect(sorted(expandAll(["b", "a", "b"]))).toEqual(["a", "b"]);
    expect(collapseAll().size).toBe(0);
    expect(collapseAll()).not.toBe(collapseAll());
  });

  it("withMounted sjednotí a bez nového id vrátí tentýž objekt", () => {
    const mounted: ReadonlySet<string> = new Set(["a"]);
    const next = withMounted(mounted, new Set(["b"]));
    expect(sorted(next)).toEqual(["a", "b"]);
    expect(sorted(mounted)).toEqual(["a"]);
    expect(withMounted(mounted, new Set(["a"]))).toBe(mounted);
    expect(withMounted(mounted, new Set())).toBe(mounted);
  });

  it("sbalení nechá editor připojený, rozbalení ho připojí", () => {
    const opened = viewWithExpanded(EMPTY_CHAPTER_VIEW, toggleChapter(EMPTY_CHAPTER_VIEW.expanded, "a"));
    expect(sorted(opened.expanded)).toEqual(["a"]);
    expect(sorted(opened.mounted)).toEqual(["a"]);
    const closed = viewWithExpanded(opened, collapseAll());
    expect(closed.expanded.size).toBe(0);
    expect(sorted(closed.mounted)).toEqual(["a"]);
    const all = viewWithExpanded(closed, expandAll(["b", "c"]));
    expect(sorted(all.mounted)).toEqual(["a", "b", "c"]);
  });

  it("expandedCount počítá jen dané kapitoly", () => {
    expect(expandedCount(["a", "b", "c"], new Set(["a", "c", "stará"]))).toBe(2);
    expect(expandedCount([], new Set(["a"]))).toBe(0);
  });
});
