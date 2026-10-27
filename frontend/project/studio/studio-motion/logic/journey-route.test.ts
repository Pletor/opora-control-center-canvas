import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { buildStudioTree } from "../../logic/studio-tree";
import { levelOf } from "../../logic/studio-level";
import type { StudioJourney } from "../../logic/studio-status";
import { hopLink, routeOnLevel, stepCard } from "./journey-route";

// Doména „web“ se třemi stránkami; „prodej“ má komponentu „form“. Vazby: úvod → zdarma → prodej a hlouběji form → úvod.
const page = (id: string) => ({ id, parentId: "web", name: id, purpose: "", kind: "node" as const, x: 0, y: 0, site: { kind: "page" as const, path: "/" + id } });
const graph: Graph = {
  nodes: [
    { id: "web", parentId: null, name: "Web", purpose: "", kind: "sector", x: 0, y: 0, site: { kind: "application", environments: [], journeys: [] } },
    page("uvod"), page("zdarma"), page("prodej"),
    { id: "form", parentId: "prodej", name: "Formulář", purpose: "", kind: "node", x: 0, y: 0 },
  ],
  edges: [
    { id: "e1", source: "uvod", target: "zdarma", carries: "navigation" },
    { id: "e2", source: "zdarma", target: "prodej", carries: "navigation" },
    { id: "e3", source: "form", target: "uvod", carries: "navigation" },
  ],
};
const tree = buildStudioTree(graph);
const journey: StudioJourney = {
  id: "kampan", name: "Kampaň", domainId: "web", pages: new Set(["uvod", "zdarma", "prodej"]),
  stepPages: new Map([["menu", "nav"], ["vstup", "uvod"], ["zdarma", "zdarma"], ["prodej", "prodej"]]), derived: undefined,
};
const place = (focus: string | null) => ({ tree, focus, links: levelOf(tree, graph, focus).links });

describe("journey route on a level", () => {
  it("maps a step to its page or to the page's ancestor on the level", () => {
    expect(stepCard(place("web"), journey, "vstup")).toBe("uvod");
    expect(stepCard(place(null), journey, "vstup")).toBe("web");
    expect(stepCard(place("web"), journey, "menu")).toBeNull();
    expect(stepCard(place("web"), journey, "neznámý")).toBeNull();
  });

  it("finds the level link a segment runs along, in its direction only", () => {
    expect(hopLink(place("web"), journey, { from: "vstup", to: "zdarma" })?.id).toBe("uvod->zdarma");
    expect(hopLink(place("web"), journey, { from: "zdarma", to: "vstup" })).toBeNull();
    expect(hopLink(place(null), journey, { from: "vstup", to: "zdarma" })).toBeNull();
    expect(hopLink(place("web"), journey, { from: "menu", to: "vstup" })).toBeNull();
  });

  it("lists route links in segment order once each, and the step cards on the level", () => {
    const hops = [{ from: "menu", to: "vstup" }, { from: "vstup", to: "zdarma" }, { from: "zdarma", to: "prodej" }, { from: "vstup", to: "zdarma" }];
    expect(routeOnLevel(place("web"), journey, hops)).toEqual({ links: ["uvod->zdarma", "zdarma->prodej"], cards: ["uvod", "zdarma", "prodej"] });
    expect(routeOnLevel(place(null), journey, hops)).toEqual({ links: [], cards: ["web"] });
  });
});
