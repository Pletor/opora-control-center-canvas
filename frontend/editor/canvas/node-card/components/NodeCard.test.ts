import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ReactFlowProvider } from "@xyflow/react";
import { describe, expect, it } from "vitest";
import { NodeCardView, type NodeCardData } from "./NodeCard";
import { cardView } from "../logic/card-model";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import type { CardDetail } from "../logic/card-lod";
import { cardFace } from "@/editor/canvas/card-face/logic/card-face";

const state = emptyDesktopState();
state.nodes.n = { phase: "build", criteria: [], steps: [], rules: [],
  blocks: [{ id: "b1", number: "1", title: "Blok", text: "Popis bloku", tags: [], todos: [], images: [], parentBlockId: "",
    state: { status: "open", condition: "", onMet: { kind: "none", targetId: "", note: "" }, onUnmet: { kind: "none", targetId: "", note: "" } },
    ports: [{ id: "p1", label: "Ano" }, { id: "p2", label: "Ne" }] }] };
const node = { id: "n", parentId: null, kind: "node" as const, name: "Karta", purpose: "Účel", x: 0, y: 0 };
const data: NodeCardData = { view: cardView(node, nodeWorkflowOf(state, "n"), 0), dimmed: false, rename: { editing: false },
  ports: { open: [] }, blocks: { disabled: false },
  face: cardFace({ nodeId: "n", sector: false, nameOf: String, decisions: [],
    card: { nodeId: "n", stage: "work", health: "ok", reason: "runs_active", executionId: "e1",
      lease: { holder: "agent:codex-2", expiresAt: "2099-01-01T00:00:00Z", epoch: 2 }, steps: { total: 7, done: 3, current: "s4" } } }) };

const render = (selected: boolean, detail: CardDetail) =>
  renderToStaticMarkup(createElement(ReactFlowProvider, null, createElement(NodeCardView, { id: "n", data, selected, detail })));

describe("NodeCard level of detail", () => {
  it("shows port editors, block tools and remove buttons only on the selected card", () => {
    const picked = render(true, "full");
    const idle = render(false, "full");
    expect(picked).toContain("node-card__port-editor");
    expect(picked).toContain("Odebrat port Ano");
    expect(picked).toContain("Posunout blok výš");
    expect(idle).not.toContain("node-card__port-editor");
    expect(idle).not.toContain("Odebrat port");
    expect(idle).not.toContain("Posunout blok výš");
    // Nevybraná karta má z bloků jen číslo, název a úchyty; psát se dá po výběru karty.
    expect(idle).not.toContain("<textarea");
    expect(picked).toContain("Popis bloku");
    expect(idle.length).toBeLessThan(picked.length);
  });

  it("draws only the glyph when zoomed out but keeps every handle so edges stay attached", () => {
    const near = render(false, "full");
    const far = render(false, "far");
    expect(far).toContain('data-detail="far"');
    expect(far).toContain("card-face--glyph");
    expect(far).not.toContain("card-face__status");
    expect(near).toContain("card-face__status");
    for (const handle of ["card-port-handle-p1", "card-port-handle-p2", "port-next-n", "port-action-n"]) {
      expect(near).toContain(handle);
      expect(far).toContain(handle);
    }
    expect(far).toContain("Karta");
    expect(far.length).toBeLessThan(near.length);
  });

  it("shows one status line from agent-state and nothing of the legacy pipeline", () => {
    const picked = render(true, "full");
    const idle = render(false, "full");
    for (const html of [picked, idle]) {
      expect(html.match(/card-face__status/g)?.length).toBe(1);
      expect(html).toContain('data-oh-card-face="n"');
      expect(html).toContain('data-oh-lease-holder="agent:codex-2"');
      expect(html).toContain("node-card--face-working");
      expect(html).toContain("3/7");
      for (const legacy of ["card-checklist", "node-card__process", "node-card__state", "node-card__proof-box", "čeká na router"]) expect(html).not.toContain(legacy);
    }
    expect(picked.match(/node-card__details/g)?.length).toBe(1);
    expect(idle).not.toContain("node-card__details");
  });
});
