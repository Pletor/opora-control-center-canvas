import { describe, expect, it } from "vitest";
import { specificationDiff } from "./specification-diff";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import SpecificationDiff from "../components/SpecificationDiff";

describe("assignment comparison", () => {
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
