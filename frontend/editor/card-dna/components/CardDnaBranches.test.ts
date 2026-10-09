import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import CardDnaAssignment from "./CardDnaAssignment";
import CardDnaCode from "./CardDnaCode";
import CardDnaWorkflow from "./CardDnaWorkflow";

const node: CanvasNode = { id: "n1", parentId: null, kind: "node", name: "DNA", purpose: "Dokázat výstup", x: 0, y: 0,
  sourceRef: { origin: "existing", path: "frontend/dna.tsx", kind: "file" }, realization: { commit: "abcdef012345", prUrl: "https://github.com/acme/repo/pull/7", verifiedAt: "2026-10-08T12:00:00Z" } };
const graph: Graph = { nodes: [node, { ...node, id: "before", name: "Předchůdce" }, { ...node, id: "after", name: "Následník" }], edges: [{ id: "in", source: "before", target: "n1" }, { id: "out", source: "n1", target: "after" }] };
const state: DesktopState = { settings: [], rules: [], decisions: [{ id: "d1", nodeId: "n1", text: "Použít existující API", pinned: true, path: "", by: "human", createdAt: "2026-10-08" }], tickets: [], nodes: { n1: { phase: "build", criteria: [], steps: [], stages: { profile: "code", items: [{ id: "s1", kind: "work", lens: "", title: "Implementace", brief: "Dodat komponentu", status: "failed", note: "Chybí test", by: "agent", approved: true, doneBy: "agent", at: "2026-10-08", retryOf: "old" }] } } } };
const data = {
  view: { kind: "node", name: "DNA", purpose: "Dokázat výstup", rows: [], waitingOnHuman: [], checks: [], goal_mode: "manual" },
  rename: { editing: false, start: () => {}, cancel: () => {}, commit: () => {} }, ports: { open: [], toggle: () => {} },
  blocks: { disabled: true, add: () => {}, move: () => {}, remove: () => {}, rename: () => {}, text: () => {}, addPort: () => {}, removePort: () => {}, writePort: () => {}, spawn: () => {} },
  dimmed: false, onTag: () => {}, source: { source: node.sourceRef!, project: "p", workspace: "w" },
  realization: { value: node.realization, status: { status: "present", at: "2026-10-08" }, disabled: true, save: async () => {} },
  assignmentWarning: { project: "p", workspace: "w", nodeId: "n1", resultId: "r1" },
  scenario: { command: "npm test", history: { latest: { command: "npm test", at: "2026-10-08", passed: 4, failed: 0, logUrl: "https://example.com/log", firstFailure: "" }, current: true } },
} as unknown as NodeCardData;
const props = { node, data, state, graph, project: "p", workspace: "w" };

describe("Card DNA detail branches", () => {
  it.each([CardDnaAssignment, CardDnaWorkflow])("zachovává rozhodnutí a spawn v obou editovatelných záložkách", Component => {
    const withPorts = { ...data, view: { ...data.view, rows: [{ id: "b", number: "1", title: "Blok", text: "", status: "open", ports: [{ id: "p", label: "Výstup" }] }] },
      blocks: { ...data.blocks, disabled: false, decidePort() {}, configureSpawn() {} } } as NodeCardData;
    const html = renderToStaticMarkup(createElement(Component, { ...props, data: withPorts }));
    expect(html).toContain('aria-label="Rozhodnutí portu"'); expect(html).toContain('aria-label="Navazující karta"');
    expect(html).not.toContain("react-flow__handle");
  });
  it("Zadání zachová přejmenování karty", () => {
    const html = renderToStaticMarkup(createElement(CardDnaAssignment, { ...props, data: { ...data, rename: { ...data.rename, editing: true } } }));
    expect(html).toContain('data-testid="card-rename-n1"'); expect(html).toContain('value="DNA"');
  });
  it("renders assignment editing, revision history, blocks, rules area and decisions", () => {
    const html = renderToStaticMarkup(createElement(CardDnaAssignment, props));
    expect(html).toContain("Zadání pro práci");
    expect(html).toContain("Historie revizí");
    expect(html).toContain("Text uzlu");
    expect(html).toContain("Bloky, podmínky a porty");
    expect(html).toContain("Použít existující API");
  });

  it("renders explicit realization, synchronization, assignment and scenario code evidence", () => {
    const html = renderToStaticMarkup(createElement(CardDnaCode, props));
    expect(html).toContain("Commit/PR");
    expect(html).toContain("abcdef012345");
    expect(html).toContain("OporaHub");
    expect(html).toContain("Zadání se změnilo");
    expect(html).toContain("E2E");
  });

  it("renders pipeline notes, retry identity, loop, blocks and both graph directions", () => {
    const html = renderToStaticMarkup(createElement(CardDnaWorkflow, props));
    expect(html).toContain("Implementace");
    expect(html).toContain("Chybí test");
    expect(html).toContain("Opakování");
    expect(html).toContain("smyčky oprav");
    expect(html).toContain("Předchůdce");
    expect(html).toContain("Následník");
  });

  it("ve workflow vrací celý upstream kontext zamítnutého portu", () => {
    const rejectedGraph = { ...graph, edges: [{ id: "in", source: "before", target: "n1", sourceBlockId: "block", sourcePortId: "port" }] } as Graph;
    const rejectedState = {
      ...state,
      nodes: { ...state.nodes, before: { blocks: [{ id: "block", ports: [{ id: "port", label: "API", status: "rejected", reason: "REJECT_REASON" }] }] } },
      decisions: [...state.decisions, { id: "old", nodeId: "before", text: "Původní předpoklad", pinned: false, path: "", by: "agent", createdAt: "2026-10-08" }, { id: "fix", nodeId: "before", text: "Opravený předpoklad", supersedes: "old", pinned: false, path: "", by: "agent", createdAt: "2026-10-09" }],
    } as unknown as DesktopState;
    const html = renderToStaticMarkup(createElement(CardDnaWorkflow, { ...props, graph: rejectedGraph, state: rejectedState }));
    expect(html).toContain("Zamítnutá větev z:");
    expect(html).toContain("Předpoklad se změnil");
    expect(html).toContain("REJECT_REASON");
    expect(html).toContain("Původní předpoklad");
  });
});
