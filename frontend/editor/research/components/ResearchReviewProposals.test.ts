import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { PreparedReviewContent } from "./ResearchReviewProposals";
import type { ReviewPreparation } from "../logic/use-review-proposals";

it("renders the immutable question, decision and exact source quotations as data", () => {
  const card = { id: "card", title: "Pinned title", revision: 7, summary: "Summary", content: "<script>unsafe()</script>",
    verification: { status: "observed" }, sources: [{ title: "Source", ref: "https://example.org", quote: "Exact source passage", location: "file:12", revision: "abc123" }] };
  const item = { snapshot: { problem: { ...card, id: "problem" }, decision: { ...card, id: "decision" }, evidence: [card],
    rationale: "Chosen because", assumptions: "Explicit assumption", constraints: "Still uncertain" } } as unknown as ReviewPreparation;
  const html = renderToStaticMarkup(createElement(PreparedReviewContent, { item }));
  expect(html).toContain("revize 7"); expect(html).toContain("Exact source passage");
  expect(html).toContain("abc123"); expect(html).toContain("Explicit assumption");
  expect(html).toContain("Still uncertain"); expect(html).not.toContain("<script>");
  expect(html).toContain("&lt;script&gt;"); expect(html).not.toContain("Potvrdit připravené posouzení");
});
