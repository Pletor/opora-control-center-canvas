import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { buildStudioTree, sectionItemId } from "../../logic/studio-tree";
import { cardView, iconFor, summaryLine } from "./card-view";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id, purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [{ name: "Vývoj", host: "web.dev" }] } }),
  node("home", "web", { purpose: "Přivítá", site: { kind: "page", path: "/", sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "" }] } }),
  node("api", "home", { card: { layer: "backend", tech: "FastAPI", section: "hero" } }), node("plain", "home"),
], edges: [] };
const tree = buildStudioTree(graph);
const item = (id: string) => tree.items.get(id)!;

describe("card view", () => {
  it("picks the icon by kind and component layer", () => {
    expect(iconFor(item("web"))).toBe("globe");
    expect(iconFor(item("home"))).toBe("layout-dashboard");
    expect(iconFor(item(sectionItemId("home", "hero")))).toBe("list-ordered");
    expect(iconFor(item("api"))).toBe("server-cog");
    expect(iconFor(item("plain"))).toBe("box");
  });

  it("says how much stands below the card", () => {
    expect(summaryLine({ children: 2, total: 7, done: 4, building: 1, holes: 0 })).toBe("4/7 stojí · 1 se staví");
    expect(summaryLine({ children: 1, total: 0, done: 0, building: 0, holes: 0 })).toBe("jen prázdné sekce");
    expect(summaryLine({ children: 0, total: 0, done: 0, building: 0, holes: 0 })).toBe("bez dětí");
  });

  it("builds the view with subtitle per kind and state label", () => {
    const status = { state: "hole" as const, summary: { children: 2, total: 2, done: 0, building: 0, holes: 3 }, ownHoles: ["x"], journeys: [] };
    expect(cardView(item("home"), status)).toEqual({ id: "home", name: "home", kind: "page", kindLabel: "Stránka", subtitle: "/", purpose: "Přivítá", icon: "layout-dashboard",
      state: "hole", stateLabel: "díra", summary: "0/2 stojí", holes: 3, children: 2, modelTarget: false });
    expect(cardView(item("api"), status, true).modelTarget).toBe(true);
    expect(cardView(item("web"), status).subtitle).toBe("web.dev");
    expect(cardView(item("api"), status).subtitle).toBe("FastAPI");
    expect(cardView(item(sectionItemId("home", "hero")), status).subtitle).toBe("hero");
  });
});
