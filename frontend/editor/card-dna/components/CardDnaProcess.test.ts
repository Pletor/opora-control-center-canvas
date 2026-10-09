import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import CardDnaProcess from "./CardDnaProcess";

vi.mock("../logic/use-dna-history", () => ({
  useDnaHistory: () => ({ brief: null, results: [], messages: [], before: null, loading: false, loadingMore: false, error: "", partial: false, loadMore: async () => {}, loadAll: async () => {}, reload: () => {} }),
}));

it("v UI nabídne starší lokální dávku pro 101 kontrol místo ztráty nejstarší události", () => {
  const node = { id: "n1", parentId: null, kind: "node", name: "DNA", purpose: "", x: 0, y: 0 } as never;
  const data = { evidence: { checksRun: Array.from({ length: 101 }, (_, index) => ({ checkId: `run-${String(index).padStart(3, "0")}`, command: "npm test", exitCode: 0, at: new Date(Date.UTC(2026, 9, 9, 0, 0, index)).toISOString() })) } } as never;
  const html = renderToStaticMarkup(createElement(CardDnaProcess, { node, data, state: { nodes: {}, decisions: [] }, graph: { nodes: [node], edges: [] }, project: "p", workspace: "w" } as never));
  expect(html).toContain("Zobrazit starší události");
  expect(html).toContain("run-100");
  expect(html).not.toContain("run-000");
  expect((html.match(/Kontrola · run-/g) ?? [])).toHaveLength(100);
});
