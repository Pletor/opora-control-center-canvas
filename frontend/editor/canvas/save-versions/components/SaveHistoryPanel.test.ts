import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import SaveHistoryPanel from "./SaveHistoryPanel";

it("distinguishes agent, human and unknown version provenance", () => {
  const html = renderToStaticMarkup(createElement(SaveHistoryPanel, {
    versions: [
      { id: "a", author: "A", createdAt: "2026-10-07T10:00:00Z", nodeCount: 2, actor: "agent", changedCardCount: 1 },
      { id: "h", author: "H", createdAt: "2026-10-07T10:00:00Z", nodeCount: 2, actor: "human", changedCardCount: 0 },
      { id: "old", author: "Old", createdAt: "2026-10-07T10:00:00Z", nodeCount: 2 },
    ], loading: false, error: "", disabled: false, onRestore: async () => {}, onPrepareRestore: async () => {}, onClose: () => {},
  }));
  expect(html).toContain("🤖 Agent");
  expect(html).toContain("👤 Člověk");
  expect(html).toContain("Změněné karty: 0");
  expect(html).toContain("Původce nedostupný");
  expect(html).toContain("Změněné karty: nedostupné");
});
