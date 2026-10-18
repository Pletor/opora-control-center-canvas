import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardRules from "./CardRules";

it("renders rule and prohibition with their text and editing controls", () => {
  const html = renderToStaticMarkup(createElement(CardRules, {
    disabled: false, write: async () => true, review: async () => true,
    rules: [{ id: "r1", text: "Keep API stable", kind: "must", scope: "node", target: "n" },
      { id: "r2", text: "Never log secrets", kind: "must_not", scope: "node", target: "n" }],
  }));
  expect(html).toContain("✓");
  expect(html).toContain("⊘");
  expect(html).toContain('title="Never log secrets"');
  expect(html).toContain("Upravit");
});

it("marks agent-written rules as muted proposals awaiting approval", () => {
  const html = renderToStaticMarkup(createElement(CardRules, {
    disabled: false, write: async () => true, review: async () => true,
    rules: [{ id: "r1", text: "Proposed", kind: "must", scope: "node", target: "n", by: "agent" },
      { id: "r2", text: "Human", kind: "must", scope: "node", target: "n" }],
  }));
  expect(html).toContain("🤖");
  expect(html).toContain("návrh agenta – čeká na schválení");
  expect(html).toContain("node-card__fold--proposal");
  expect(html.match(/Schválit/g)).toHaveLength(1);
  expect(html.match(/Zamítnout/g)).toHaveLength(1);
});
