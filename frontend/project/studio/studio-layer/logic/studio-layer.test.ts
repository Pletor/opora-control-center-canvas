import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { buildStudioTree, sectionItemId } from "../../logic/studio-tree";
import type { StudioFacts } from "../../logic/studio-status";
import { bindingCards, effectiveLayer, modelDomainOf, readStudioLayer, withStudioLayer } from "./studio-layer";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id.toUpperCase(), purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
  node("home", "web", { site: { kind: "page", path: "/", sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "" }] } }),
  node("c1", "home", { card: { section: "hero" } }),
  node("api", "web"),
  node("admin", null, { kind: "sector", site: { kind: "application", environments: [] } }),
  node("other", "admin"),
], edges: [] };
const facts: StudioFacts = { done: new Set(["c1"]), building: new Set(), holes: new Map(), journeys: [] };

describe("studio layer", () => {
  const tree = buildStudioTree(graph);

  it("reads and writes the layer in the address, reality being the default", () => {
    expect(readStudioLayer(new URLSearchParams("studioLayer=model"))).toBe("model");
    expect(readStudioLayer(new URLSearchParams("studioLayer=x"))).toBe("reality");
    expect(withStudioLayer(new URLSearchParams("a=1"), "model").toString()).toBe("a=1&studioLayer=model");
    expect(withStudioLayer(new URLSearchParams("a=1&studioLayer=model"), "reality").toString()).toBe("a=1");
  });

  it("finds the domain of the focus and falls back to reality on the project level", () => {
    expect(modelDomainOf(tree, null)).toBeNull();
    expect(modelDomainOf(tree, "web")).toBe("web");
    expect(modelDomainOf(tree, sectionItemId("home", "hero"))).toBe("web");
    expect(effectiveLayer("model", null)).toBe("reality");
    expect(effectiveLayer("model", "web")).toBe("model");
    expect(effectiveLayer("reality", "web")).toBe("reality");
  });

  it("offers pages and components of the domain with their real state, never sections or other domains", () => {
    expect(bindingCards(tree, facts, "web")).toEqual([
      { id: "home", name: "HOME", kindLabel: "Stránka", state: "plan", stateLabel: "plán" },
      { id: "c1", name: "C1", kindLabel: "Komponenta", state: "done", stateLabel: "hotovo" },
      { id: "api", name: "API", kindLabel: "Komponenta", state: "plan", stateLabel: "plán" },
    ]);
  });
});
