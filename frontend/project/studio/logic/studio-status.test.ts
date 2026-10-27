import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DerivedJourney } from "@/project/architecture-editor/domain-map/logic/derived-journeys";
import { buildStudioTree, sectionItemId } from "./studio-tree";
import { cardStatus, journeysOf, type StudioFacts, type StudioJourney } from "./studio-status";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id, purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
  node("home", "web", { site: { kind: "page", path: "/", sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "" }] } }),
  node("c1", "home", { card: { section: "hero" } }), node("c2", "home", { card: { section: "hero" } }), node("c3", "home"),
], edges: [] };
const run = (passed: boolean, stale = false): DerivedJourney => ({ applicationId: "web", id: "j", missing: [], segments: [], lastRun: { at: "2026-10-27T10:00:00Z", passed, stale, command: "x", failed: passed ? 0 : 1 } });
const journey = (derived: DerivedJourney | undefined): StudioJourney => ({ id: "j", name: "Kampaň", domainId: "web", pages: new Set(["home"]), derived });
const facts = (extra: Partial<StudioFacts> = {}): StudioFacts => ({ done: new Set(), building: new Set(), holes: new Map(), journeys: [], ...extra });

describe("studio card status", () => {
  const tree = buildStudioTree(graph);
  const item = (id: string) => tree.items.get(id)!;

  it("aggregates children: done, building and holes below the card", () => {
    const status = cardStatus(tree, item("home"), facts({ done: new Set(["c1", "c3"]), building: new Set(["c2"]), holes: new Map([["home", ["bez cíle"]], ["c3", ["bez stavu"]]]) }));
    expect(status.summary).toEqual({ children: 2, total: 3, done: 2, building: 1, holes: 2 });
    expect(status.state).toBe("building");
    expect(status.ownHoles).toEqual(["bez cíle"]);
  });

  it("derives plan, hole, done and verified in that order of evidence", () => {
    expect(cardStatus(tree, item("c3"), facts()).state).toBe("plan");
    expect(cardStatus(tree, item("c3"), facts({ holes: new Map([["c3", ["díra"]]]), done: new Set(["c3"]) })).state).toBe("hole");
    expect(cardStatus(tree, item("c3"), facts({ done: new Set(["c3"]) })).state).toBe("done");
    expect(cardStatus(tree, item("c3"), facts({ done: new Set(["c3"]), journeys: [journey(run(true))] })).state).toBe("verified");
    expect(cardStatus(tree, item("c3"), facts({ done: new Set(["c3"]), journeys: [journey(run(true, true))] })).state).toBe("done");
    expect(cardStatus(tree, item("c3"), facts({ done: new Set(["c3"]), journeys: [journey(run(false))] })).state).toBe("done");
  });

  it("treats a section as done only when all its components are done", () => {
    const section = item(sectionItemId("home", "hero"));
    expect(cardStatus(tree, section, facts({ done: new Set(["c1"]) })).state).toBe("plan");
    expect(cardStatus(tree, section, facts({ done: new Set(["c1", "c2"]) })).state).toBe("done");
  });

  it("finds journeys of the domain and of the card's page", () => {
    const all = [journey(undefined), { ...journey(undefined), id: "other", pages: new Set(["elsewhere"]) }];
    expect(journeysOf(item("web"), all).map((entry) => entry.id)).toEqual(["j", "other"]);
    expect(journeysOf(item("c1"), all).map((entry) => entry.id)).toEqual(["j"]);
  });
});
