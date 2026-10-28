import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DerivedJourney } from "../../domain-map/logic/derived-journeys";
import { cardIcon, cardLife, cardStates, holesLabel } from "./card-state";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id, purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [], journeys: [{ id: "j", name: "Kampaň", steps: [{ id: "s1", page: "home" }] }] } as CanvasNode["site"] }),
  node("home", "web", { site: { kind: "page", path: "/" } }),
  node("form", "home", { card: { layer: "frontend" } }), node("api", "home", { card: { layer: "backend" } }),
  node("zone", "home", { kind: "area" }), node("note", "home", { kind: "comment" }),
], edges: [] };
const facts = { done: new Set<string>(), building: new Set<string>(), holes: new Map<string, string[]>(), journeys: [] };

describe("card state for architecture cards", () => {
  it("gives Studio states to domain, page and components, none to areas and comments", () => {
    const states = cardStates(graph, { ...facts, done: new Set(["form", "api"]), building: new Set(), holes: new Map([["api", ["bez stavu"]]]) });
    expect(states.get("form")).toEqual({ state: "done", label: "hotovo", summary: "bez dětí", holes: 0, guards: null });
    expect(states.get("api")?.state).toBe("hole");
    expect(states.get("home")).toMatchObject({ state: "plan", summary: "2/2 stojí", holes: 1 });
    expect(states.has("zone")).toBe(false);
    expect(states.has("note")).toBe(false);
  });

  it("marks building through the subtree like Studio", () => {
    const states = cardStates(graph, { ...facts, building: new Set(["api"]) });
    expect(states.get("api")?.label).toBe("staví se");
    expect(states.get("home")?.summary).toBe("0/2 stojí · 1 se staví");
  });

  it("carries guard findings of the card and its children for the badge", () => {
    const guards = new Map([["api", { count: 2, severity: "warn" as const }], ["form", { count: 1, severity: "block" as const }]]);
    const states = cardLife({ graph, doneIds: [], work: null, check: null, derived: null, guards }).states;
    expect(states.get("api")?.guards).toEqual({ count: 2, severity: "warn" });
    expect(states.get("home")?.guards).toEqual({ count: 3, severity: "block" });
    expect(states.get("web")?.guards).toEqual({ count: 3, severity: "block" });
  });

  it("verifies a done page only with a passed, fresh run", () => {
    const run: DerivedJourney = { applicationId: "web", id: "j", missing: [], segments: [], lastRun: { at: "t", passed: true, stale: false, command: "x", failed: 0 } };
    const life = cardLife({ graph, doneIds: ["home", "form", "api"], work: null, check: null, derived: [run] });
    expect(life.states.get("home")?.state).toBe("verified");
    expect(life.journeys?.map((journey) => journey.id)).toEqual(["j"]);
    expect(cardLife({ graph, doneIds: [], work: null, check: null, derived: null }).journeys).toBeNull();
  });

  it("picks Lucide icons by kind and layer", () => {
    expect(["web", "home", "form", "api"].map((id) => cardIcon(graph.nodes.find((item) => item.id === id)!))).toEqual(["globe", "layout-dashboard", "monitor", "server-cog"]);
    expect(cardIcon(node("s", "home", { kind: "sector" }))).toBe("list-ordered");
  });

  it("declines holes in Czech", () => {
    expect([1, 3, 5].map(holesLabel)).toEqual(["1 díra", "3 díry", "5 děr"]);
  });
});
