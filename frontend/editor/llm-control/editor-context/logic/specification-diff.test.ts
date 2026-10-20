import { describe, expect, it } from "vitest";
import { specificationDiff } from "./specification-diff";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import SpecificationDiff from "../components/SpecificationDiff";

describe("assignment comparison", () => {
  const graph = (nodes: unknown[]) => ({ graph: { nodes } });
  it("reports an inserted node only once and still finds an existing node edit", () => {
    const existing = { id: "b", label: "before" };
    const inserted = { id: "a", label: "new" };
    expect(specificationDiff(graph([existing]), graph([inserted, existing])).changes).toEqual([
      { path: "/graph/nodes/id=a", before: undefined, after: inserted, kind: "added" },
    ]);
    expect(specificationDiff(graph([existing]), graph([inserted, { ...existing, label: "after" }])).changes).toEqual([
      { path: "/graph/nodes/id=a", before: undefined, after: inserted, kind: "added" },
      { path: "/graph/nodes/id=b/label", before: "before", after: "after", kind: "changed" },
    ]);
  });
  it("reports deletion without changes to surviving nodes, including empty collections", () => {
    const a = { id: "a" }, b = { id: "b" };
    for (const remaining of [[b], []]) {
      expect(specificationDiff(graph([a, ...remaining]), graph(remaining)).changes).toEqual([
        { path: "/graph/nodes/id=a", before: a, after: undefined, kind: "removed" },
      ]);
      expect(specificationDiff(graph(remaining), graph([a, ...remaining])).changes).toEqual([
        { path: "/graph/nodes/id=a", before: undefined, after: a, kind: "added" },
      ]);
    }
  });
  it.each([
    ["nodes", "id"], ["edges", "id"], ["cards", "nodeId"], ["drawings", "layer"],
  ])("matches %s by %s while ignoring reordering", (collection, key) => {
    const wrap = (values: unknown[]) => key === "id" ? { graph: { [collection]: values } } : { [collection]: values };
    const a = { [key]: key === "layer" ? "" : "a", value: 1 }, b = { [key]: "b", value: 2 };
    expect(specificationDiff(wrap([a, b]), wrap([b, a])).changes).toEqual([]);
    expect(specificationDiff(wrap([a, b]), wrap([{ ...b, value: 3 }, a])).changes).toEqual([
      { path: `${key === "id" ? "/graph" : ""}/${collection}/${key}=b/value`, before: 2, after: 3, kind: "changed" },
    ]);
  });
  it.each([
    [{ id: "duplicate", value: 1 }, { id: "duplicate", value: 2 }],
    [{ id: "a" }, { value: 2 }],
    [{ id: "a" }, { id: "" }],
    [{ id: "a" }, { id: null }],
    [{ id: "a" }, { id: 2 }],
    [{ id: "a" }, { id: " " }],
  ])("falls back to positions for invalid or duplicate keys: %j, %j", (a, b) => {
    const changes = specificationDiff(graph([a, b]), graph([b, a])).changes;
    expect(changes.length).toBeGreaterThan(0);
    expect(changes.every(change => /^\/graph\/nodes\/[01]\//.test(change.path))).toBe(true);
  });
  it("requires unique valid keys on both sides", () => {
    for (const [before, after] of [
      [[{ id: "a" }, { id: "b" }], [{ id: "a" }, { id: "a" }]],
      [[{ id: "a" }, { id: "a" }], [{ id: "a" }, { id: "b" }]],
    ]) expect(specificationDiff(graph(before), graph(after)).changes[0].path).toBe("/graph/nodes/1/id");
  });
  it("preserves order for navigation pages, primitive arrays, and other ID arrays", () => {
    const a = { nodeId: "a" }, b = { nodeId: "b" };
    expect(specificationDiff({ navigation: [{ pages: [a, b] }] }, { navigation: [{ pages: [b, a] }] }).changes).toHaveLength(2);
    expect(specificationDiff([1, 2], [2, 1]).changes).toHaveLength(2);
    expect(specificationDiff([{ id: "a" }, { id: "b" }], [{ id: "b" }, { id: "a" }]).changes).toHaveLength(2);
  });
  it("escapes entity keys and retains the overflow signal", () => {
    expect(specificationDiff(graph([{ id: "a~/b", value: 1 }]), graph([{ id: "a~/b", value: 2 }])).changes[0].path).toBe("/graph/nodes/id=a~0~1b/value");
    expect(specificationDiff(graph([]), graph([{ id: "a" }, { id: "b" }]), 1).truncated).toBe(true);
  });
  it("explains the count as fields or items rather than editing frequency", () => {
    const html = renderToStaticMarkup(createElement(SpecificationDiff, { before: {}, after: {} }));
    expect(html).toContain("rozdílná pole");
    expect(html).toContain("nikoli počet úprav v čase");
  });
  it("ignores object key order and distinguishes removed, added and changed fields", () => {
    expect(specificationDiff({ a: 1, b: 2 }, { b: 2, a: 1 }).changes).toEqual([]);
    expect(specificationDiff({ gone: "x", cards: [{ goal: "old" }] }, { added: true, cards: [{ goal: "new" }] }).changes).toEqual([
      { path: "/added", before: undefined, after: true, kind: "added" },
      { path: "/cards/0/goal", before: "old", after: "new", kind: "changed" },
      { path: "/gone", before: "x", after: undefined, kind: "removed" },
    ]);
  });
  it("shows overflow explicitly and preserves null versus missing", () => {
    expect(specificationDiff({}, { a: null, b: 1 }, 1)).toEqual({ changes: [{ path: "/a", before: undefined, after: null, kind: "added" }], truncated: true });
  });
  it("renders the old and current text safely", () => {
    const html = renderToStaticMarkup(createElement(SpecificationDiff, { before: { goal: "<script>old</script>" }, after: { goal: "New goal" } }));
    expect(html).toContain("/goal");
    expect(html).toContain("New goal");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });
  it("does not treat an unavailable legacy snapshot as an empty assignment", () => {
    expect(renderToStaticMarkup(createElement(SpecificationDiff, { before: null, after: { goal: "x" } }))).toContain("není dostupné");
  });
});
