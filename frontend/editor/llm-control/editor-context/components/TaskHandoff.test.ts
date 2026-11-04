import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import TaskHandoff from "./TaskHandoff";
import type { AgentTaskRequest } from "./TaskHandoff";

vi.mock("@/shared/types/logic/types", () => ({ api: vi.fn() }));
vi.mock("@/shared/desktop-state/logic/api", () => ({ fetchNodeBrief: vi.fn(() => new Promise(() => {})) }));

const request: AgentTaskRequest = { project: "ample", workspace: "draft", layer: null, nodeId: "n-1", nodeName: "4.2 Obec a okres", source: "canvas", text: "", requestedAt: "2026-10-15T10:20:00Z" };

describe("TaskHandoff", () => {
  // Statický render: ověřuje jen název dialogu, nadpis, zavření a počáteční hlášku (efekty, fokus a Escape neběží).
  it("dialog nese název Balíček karty v aria-label, nadpisu i zavření a začíná hláškou o načítání", () => {
    const html = renderToStaticMarkup(createElement(TaskHandoff, { request, onClose: () => {}, onSaved: () => {} }));
    expect(html).toContain('aria-label="Balíček karty"');
    expect(html).toContain("<h2>Balíček karty · 4.2 Obec a okres</h2>");
    expect(html).toContain('aria-label="Zavřít balíček karty"');
    expect(html).not.toContain("Předat zadání");
    expect(html).toContain("Balíček obsahuje uložené zadání");
    expect(html).toContain("Načítám uložené zadání…");
  });
});
