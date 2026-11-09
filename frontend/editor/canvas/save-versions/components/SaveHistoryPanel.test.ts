import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
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


it("selects the requested immutable version and shows its contents without restoring", () => {
  const onRestore = vi.fn(); const onPrepareRestore = vi.fn();
  const html = renderToStaticMarkup(createElement(SaveHistoryPanel, {
    versions: [{ id: "a", author: "A", createdAt: "2026-10-07T10:00:00Z", nodeCount: 1 }],
    initialSelected: "a", reviewNodes: [{ id: "n", name: "Exact historical card" }],
    loading: false, error: "", disabled: false, onRestore, onPrepareRestore, onClose: () => {},
  }));
  expect(html).toContain('aria-selected="true"');
  expect(html).toContain("Exact historical card");
  expect(onRestore).not.toHaveBeenCalled(); expect(onPrepareRestore).not.toHaveBeenCalled();
});
