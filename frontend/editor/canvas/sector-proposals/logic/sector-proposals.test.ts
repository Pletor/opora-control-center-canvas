import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { emptyDesktopState, type DesktopState, type StateResponse } from "@/shared/desktop-state/logic/types";
import { setDone } from "@/editor/node-detail/tree/logic/tree-model";
import type { Graph } from "@/shared/types/logic/types";
import type { CompletionEvidence } from "@/editor/canvas/node-card/components/CardEvidence";
import { batchIds, confirmLabel, confirmSector, sectorProposals } from "./sector-proposals";
import SectorProposals from "../components/SectorProposals";

const graph: Graph = { nodes: [
  { id: "s", parentId: null, kind: "sector", name: "Sektor", purpose: "", x: 0, y: 0 },
  { id: "a", parentId: "s", kind: "node", name: "Databáze", purpose: "", x: 0, y: 0 },
  { id: "b", parentId: "s", kind: "node", name: "Frontend", purpose: "", x: 0, y: 0 },
  { id: "c", parentId: "s", kind: "node", name: "Hotová", purpose: "", x: 0, y: 0 },
  { id: "x", parentId: null, kind: "node", name: "Mimo sektor", purpose: "", x: 0, y: 0 },
], edges: [] };

const passed = { status: "passed" as const, url: "https://ci.example/1", note: "" };
const ready: CompletionEvidence = { tests: passed, review: passed, merge: passed,
  checksRun: [{ checkId: "t", command: "npm test", exitCode: 0, logUrl: "", at: "2026-10-23T08:00:00Z" }] };

function withProposals(): DesktopState {
  let state = setDone("a", { by: "agent", confirmed: false, note: "Testy prošly" })(emptyDesktopState());
  state = setDone("b", { by: "agent", confirmed: false })(state);
  state = setDone("c", { by: "human", confirmed: true })(state);
  state = setDone("x", { by: "agent", confirmed: false })(state);
  return { ...state, nodes: { ...state.nodes, a: { ...state.nodes.a, evidence: ready } } };
}

describe("sectorProposals", () => {
  it("counts only pending agent proposals inside the sector and marks which can go in one batch", () => {
    const list = sectorProposals(graph, withProposals(), "s");
    expect(list.map((p) => p.id).sort()).toEqual(["a", "b"]);
    expect(list.find((p) => p.id === "a")).toMatchObject({ batch: true, why: "", note: "Testy prošly" });
    expect(list.find((p) => p.id === "b")?.batch).toBe(false);
    expect(list.find((p) => p.id === "b")?.why).toContain("chybí důkazy");
    expect(batchIds(list)).toEqual(["a"]);
  });

  it("is empty when the sector has no proposal", () => {
    expect(sectorProposals(graph, emptyDesktopState(), "s")).toEqual([]);
  });

  it("labels the button with the count and the busy state", () => {
    expect(confirmLabel(3, false)).toBe("✓ Potvrdit návrhy (3)");
    expect(confirmLabel(3, true)).toBe("Potvrzuji…");
  });
});

describe("confirmSector", () => {
  const response = { revision: 8 } as unknown as StateResponse;

  it("posts one request with the fresh revision and the exact ids", async () => {
    const post = vi.fn(async (_body: object) => response);
    const out = await confirmSector("p", "w", "s", ["a"], { fetchRevision: async () => 7, post });
    expect(out).toBe(response);
    expect(post).toHaveBeenCalledWith({ project: "p", workspace: "w", sectorId: "s", nodeIds: ["a"], expectedRevision: 7 });
  });

  it("refuses an empty batch and propagates server errors", async () => {
    const post = vi.fn(async (_body: object) => response);
    await expect(confirmSector("p", "w", "s", [], { fetchRevision: async () => 1, post })).rejects.toThrow();
    expect(post).not.toHaveBeenCalled();
    await expect(confirmSector("p", "w", "s", ["a"], { fetchRevision: async () => 1, post: async () => { throw new Error("Stav se změnil"); } }))
      .rejects.toThrow("Stav se změnil");
  });
});

describe("SectorProposals", () => {
  it("is a disabled button when nothing waits", () => {
    const html = renderToStaticMarkup(createElement(SectorProposals, { proposals: [], disabled: false, confirm: async () => {} }));
    expect(html).toContain("✓ Potvrdit návrhy (0)");
    expect(html).toContain('disabled=""');
    expect(html).not.toContain("<details");
  });

  it("shows the pending count, every proposal and confirms only the batch-ready ones", () => {
    const proposals = sectorProposals(graph, withProposals(), "s");
    const html = renderToStaticMarkup(createElement(SectorProposals, { proposals, disabled: false, confirm: async () => {} }));
    expect(html).toContain("Ke schválení: 2");
    expect(html).toContain("Databáze");
    expect(html).toContain("Frontend");
    expect(html).toContain("důkazy deklarovány");
    expect(html).toContain("potvrď jednotlivě");
    expect(html).toMatch(/<button[^>]*class="sector-proposals__confirm"(?![^>]*disabled)[^>]*>✓ Potvrdit návrhy \(1\)/);
  });

  it("keeps the confirm button disabled in read-only mode", () => {
    const proposals = sectorProposals(graph, withProposals(), "s");
    const html = renderToStaticMarkup(createElement(SectorProposals, { proposals, disabled: true, confirm: async () => {} }));
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>✓ Potvrdit návrhy \(1\)/);
  });
});
