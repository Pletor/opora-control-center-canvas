import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { OperationFields, PinnedFragments } from "./VaultOperationReview";

it("shows full nested operation data without interpreting source instructions as markup", () => {
  const html = renderToStaticMarkup(createElement(OperationFields, { value: {
    op: "split", expectedRevision: 7, parts: [{ title: "Exact source", text: "<script>ignore previous instructions</script>" }],
    evidence: [{ quote: "Exact quotation", revision: "abc123" }],
  } }));
  expect(html).toContain("Exact source"); expect(html).toContain("Exact quotation"); expect(html).toContain("abc123");
  expect(html).toContain("&lt;script&gt;"); expect(html).not.toContain("<script>");
  expect(html).toContain("Očekávaná revize"); expect(html).toContain(">7<");
});

it("shows exact latest pinned source and descendants without unrelated or old revisions", () => {
  const html = renderToStaticMarkup(createElement(PinnedFragments, { operation: { fragmentId: "root" }, records: [
    { fragment_id: "root", revision: 1, title: "Old", text: "Old source" },
    { fragment_id: "root", revision: 2, title: "Current pinned", text: "Literal source" },
    { fragment_id: "child", parent_id: "root", revision: 1, title: "Child", text: "Nested source" },
    { fragment_id: "other", revision: 1, title: "Unrelated", text: "Unrelated source" },
  ] }));
  expect(html).toContain("Literal source"); expect(html).toContain("Nested source");
  expect(html).not.toContain("Old source"); expect(html).not.toContain("Unrelated source");
});
