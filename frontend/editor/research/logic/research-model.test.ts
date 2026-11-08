import { describe, expect, it } from "vitest";
import { filterResearch, researchLayout, researchPositions, safeDrawingPreview, sourceUrl } from "./research-model";
import { researchUrls, requestGate } from "./research-api";
import type { ResearchEdge, ResearchHeader } from "./research-types";
const card = (id: string, topicPath = ["Přihlášení", "UX/UI"]): ResearchHeader => ({ id, revision: 1, title: id, summary: "Podklady k řešení", topicPath, kind: "finding", status: "open", verification: { status: "unverified", method: "", at: "" }, platforms: ["youtube"], sourceCount: 1, refs: { questionIds: ["q-login"], ticketIds: [], nodeIds: [], fragmentIds: [], sessionIds: [], attachmentIds: [] }, archived: false, createdAt: "2026-11-08", updatedAt: "2026-11-08", by: "srdce" });
const edge = (fromId: string, toId: string): ResearchEdge => ({ id: `${fromId}-${toId}`, revision: 1, fromId, toId, relation: "continues_to", reason: "Vzhled nevysvětluje ověřování identity", resolved: "Vzhled formuláře", missing: "Životní cyklus relace", evidenceIds: [], archived: false });
describe("research context and paths", () => {
  it("compacts filtered topics without hidden rows or depth and preserves source identities", () => {
    const hidden = Array.from({ length: 60 }, (_, index) => card(`hidden-${index}`, ["A hidden topic"]));
    const cards = [...hidden, card("selected-a", ["Z topic"]), card("selected-b", ["Z topic"])];
    const edges = [edge("hidden-0", "selected-a"), edge("selected-a", "selected-b")];
    const before = JSON.stringify({ cards, edges });
    const result = researchLayout(cards, edges, "", JSON.stringify(["Z topic"]), "");
    expect(result.cards.map(item => item.id)).toEqual(["selected-a", "selected-b"]);
    expect(result.edges.map(item => item.id)).toEqual(["selected-a-selected-b"]);
    expect(result.positions.get("selected-a")).toEqual({ x: 0, y: 0 });
    expect(result.positions.get("selected-b")).toEqual({ x: 420, y: 0 });
    expect(JSON.stringify({ cards, edges })).toBe(before);
    expect(researchLayout(cards, edges, "no-match", "", "").positions.size).toBe(0);
    expect(researchLayout(cards, edges, "", "", "").positions).toEqual(researchPositions(cards, edges));
  });
  it("keeps problem branches separate and can find question IDs", () => {
    const ux = card("ux"), logic = card("logic", ["Přihlášení", "Logika"]);
    expect(filterResearch([ux, logic], "Q-LOGIN", JSON.stringify(ux.topicPath), "youtube").map(item => item.id)).toEqual(["ux"]);
    expect(filterResearch([ux, logic], "", "", "facebook")).toEqual([]);
    expect(filterResearch([ux, logic], "logika", "", "").map(item => item.id)).toEqual(["logic"]);
  });
  it("places the semantic continuation to the right, retaining parallel findings", () => {
    const cards = [card("ux"), card("logic"), card("data")]; const edges = [edge("ux", "logic"), edge("ux", "data")];
    const positions = researchPositions(cards, edges);
    expect(positions.get("logic")!.x).toBeGreaterThan(positions.get("ux")!.x);
    expect(positions.get("logic")!.y).not.toBe(positions.get("data")!.y);
    expect(researchPositions([...cards].reverse(), edges)).toEqual(positions);
  });
  it("does not lose cyclic or disconnected findings, ignoring archived and dangling edges", () => {
    const cards = [card("a"), card("b"), card("c")];
    const positions = researchPositions(cards, [edge("a", "b"), edge("b", "a"), edge("missing", "a"), { ...edge("a", "c"), archived: true }]);
    expect(positions.size).toBe(3); expect(new Set([...positions.values()].map(item => `${item.x}:${item.y}`)).size).toBe(3);
    expect(positions.get("c")!.x).toBe(0);
  });
});
describe("safe evidence references", () => {
  it("never makes active-content or local source references clickable", () => {
    expect(sourceUrl("https://example.org/doc?q=1")).toBe("https://example.org/doc?q=1");
    for (const ref of ["javascript:alert(1)", "data:text/html,<script>", "file:///secret", "src/auth.py:32"]) expect(sourceUrl(ref)).toBeNull();
  });
  it("previews only matching supported raster MIME and data URL", () => {
    const file = { id: "screen", mimeType: "image/png", dataURL: "data:image/png;base64,abc", created: 1 };
    expect(safeDrawingPreview(file)).toBe(file.dataURL);
    expect(safeDrawingPreview({ ...file, dataURL: "data:image/svg+xml;base64,abc" })).toBeNull();
    expect(safeDrawingPreview({ ...file, mimeType: "image/svg+xml", dataURL: "data:image/svg+xml;base64,abc" })).toBeNull();
    expect(safeDrawingPreview({ ...file, dataURL: "https://tracker.invalid/img" })).toBeNull();
  });
});
describe("scoped research requests", () => {
  it("encodes scope and IDs for full and historical detail", () => {
    const scope = { project: "p&other", workspace: "branch/name" };
    const url = new URL(researchUrls.detail(scope, "card/one", 2), "https://opora.local");
    expect(url.pathname).toBe("/api/research/cards/card%2Fone"); expect(url.searchParams.get("project")).toBe(scope.project);
    expect(url.searchParams.get("workspace")).toBe(scope.workspace); expect(url.searchParams.get("revision")).toBe("2");
    expect(researchUrls.edge(scope, "e", 3)).toContain("revision=3");
    expect(researchUrls.overview(scope, false)).toContain("archived=0");
  });
  it("rejects a slower earlier response and responses after scope teardown", async () => {
    const gate = requestGate(); const applied: string[] = [];
    let finish!: () => void;
    const old = gate.begin(); const pending = new Promise<void>(resolve => { finish = resolve; }).then(() => { if (gate.accepts(old)) applied.push("old project"); });
    const recent = gate.begin(); if (gate.accepts(recent)) applied.push("current project"); finish(); await pending;
    gate.invalidate(); expect(gate.accepts(recent)).toBe(false); expect(applied).toEqual(["current project"]);
  });
});
