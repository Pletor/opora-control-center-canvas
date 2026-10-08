import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ReactFlowProvider } from "@xyflow/react";
import NodeCard from "./NodeCard";

const rows = Array.from({ length: 8 }, (_, index) => ({ id: `b${index}`, number: String(index + 1), title: "Blok", status: "open" as const, text: "Popis", ports: Array.from({ length: 8 }, (_, port) => ({ id: `p${index}-${port}`, label: "Port" })) }));
const handlers = { disabled: false, add() {}, move() {}, remove() {}, rename() {}, text() {}, addPort() {}, renamePort() {}, removePort() {} };

describe("NodeCard compact", () => {
  it("renders 200 runs and 8×8 ports without mounting an editor", () => {
    const data: any = { view: { kind: "node", name: "GOAL", purpose: "Cíl", phase: "build", phaseLabel: "build", tags: [], hiddenTags: 0, children: 0, actions: 0, rules: 0, materials: 0, openBlocks: 8, waitingOnHuman: [{ blockId: "b1", ask: "Potvrď nasazení" }], blocks: 8, rows, checks: [{ id: "one", command: "test one" }, { id: "two", command: "test two" }, { id: "three", command: "test three" }], closed: false, doneProposed: false, cardLayer: null, cardStatus: null, cardModel: null, cardEffort: null }, blocks: handlers, ports: { open: [], toggle() {} }, dimmed: false, onTag() {}, evidence: { checksRun: Array.from({ length: 200 }, (_, index) => ({ checkId: index === 0 ? "one" : "two", command: "test", exitCode: index === 0 ? 1 : 0, logUrl: "", at: "" })) }, assignmentWarning: { project: "p", workspace: "w", nodeId: "goal", resultId: "r" }, realization: { value: { commit: "abcdef123456" }, disabled: false, save: async () => {} }, usage: { tokens: 1234 }, lease: { owner: "Agent A", expiresAt: Date.now() / 1000 + 90, serverOffset: 0, active: true } };
    const html = renderToStaticMarkup(createElement(ReactFlowProvider, null, createElement(NodeCard as any, { id: "goal", data, selected: true })));
    expect(html).not.toMatch(/<(input|textarea|select)\b/);
    expect((html.match(/react-flow__handle/g) ?? []).length).toBeGreaterThanOrEqual(64);
    expect(html).toContain("1/3");
    expect(html).toContain("1 selhání");
    expect(html).toContain("zadání se změnilo");
    expect(html).toContain("abcdef1");
    expect(html).toMatch(/1.?234/);
    expect(html).toContain("Čeká na tebe");
  });
});
