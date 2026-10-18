import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ReactFlowProvider } from "@xyflow/react";
import { describe, expect, it } from "vitest";
import { NodeCardView, type NodeCardData } from "./NodeCard";
import { cardView } from "../logic/card-model";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import type { CardDetail } from "../logic/card-lod";
import { processView } from "../logic/card-process";
import { cardState } from "../logic/card-state";

const state = emptyDesktopState();
state.nodes.n = { phase: "build", criteria: [], steps: [], rules: [],
  blocks: [{ id: "b1", number: "1", title: "Blok", text: "Popis bloku", tags: [], todos: [], images: [], parentBlockId: "",
    state: { status: "open", condition: "", onMet: { kind: "none", targetId: "", note: "" }, onUnmet: { kind: "none", targetId: "", note: "" } },
    ports: [{ id: "p1", label: "Ano" }, { id: "p2", label: "Ne" }] }] };
const node = { id: "n", parentId: null, kind: "node" as const, name: "Karta", purpose: "Účel", x: 0, y: 0 };
const data: NodeCardData = { view: cardView(node, nodeWorkflowOf(state, "n"), 0), dimmed: false, rename: { editing: false },
  ports: { open: [] }, blocks: { disabled: false }, checklist: [{ key: "goal", label: "Cíl", state: "yes", hint: "" }] };

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
    // Text bloku jde dál psát i v nevybrané kartě.
    expect(idle).toContain("Popis bloku");
    expect(idle.length).toBeLessThan(picked.length);
  });

  it("drops textareas and extras when zoomed out but keeps every handle so edges stay attached", () => {
    const near = render(false, "full");
    const far = render(false, "far");
    expect(far).toContain('data-detail="far"');
    expect(far).not.toContain("<textarea");
    expect(far).not.toContain("node-card__foot");
    expect(near).toContain("card-checklist");
    expect(far).not.toContain("card-checklist");
    for (const handle of ["card-port-handle-p1", "card-port-handle-p2", "port-next-n", "port-action-n"]) {
      expect(near).toContain(handle);
      expect(far).toContain(handle);
    }
    expect(far).toContain("Karta");
    expect(far.length).toBeLessThan(near.length);
  });

  it("keeps the process, state line and one details fold in their places", () => {
    const process = processView({ profile: "code", items: [] }, undefined, []);
    const line = cardState({ closed: false, doneProposed: true, process, work: { id: "n", name: "Karta", status: "proposed", agent: "", startedAt: null,
      lastActivity: null, touched: null, waitingOnHuman: [], blockedBy: [{ id: "x", name: "Jiná" }] } });
    const withState: NodeCardData = { ...data, process, state: line, completion: { note: "hotovo", pending: 0 }, evidence: undefined };
    const picked = renderToStaticMarkup(createElement(ReactFlowProvider, null, createElement(NodeCardView, { id: "n", data: withState, selected: true, detail: "full" })));
    const idle = renderToStaticMarkup(createElement(ReactFlowProvider, null, createElement(NodeCardView, { id: "n", data: withState, selected: false, detail: "full" })));
    for (const html of [picked, idle]) {
      expect(html.indexOf("node-card__process")).toBeLessThan(html.indexOf("node-card__state"));
      expect(html.indexOf("node-card__state")).toBeLessThan(html.indexOf("card-checklist"));
      expect(html).toContain("Ke schválení");
      expect(html).toContain("Potvrdit");
      expect(html.match(/node-card__proof-box/g)?.length).toBe(4);
    }
    expect(picked.match(/node-card__details/g)?.length).toBe(1);
    expect(picked.indexOf("node-card__blocks")).toBeLessThan(picked.indexOf("node-card__details"));
    expect(picked).toContain("Podrobnosti");
    expect(idle).not.toContain("node-card__details");
    expect(picked).not.toContain("Upravit důkazy");
  });
});
