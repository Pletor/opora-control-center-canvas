import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { normalizeWorkStatus } from "@/project/architecture-editor/live-status/logic/live-model";
import { buildingNodes, holesByNode, studioJourneys } from "./studio-facts";

const graph: Graph = {
  nodes: [
    { id: "web", parentId: null, name: "Web", purpose: "", kind: "sector", x: 0, y: 0, site: { kind: "application", environments: [], journeys: [
      { id: "j1", name: "Kampaň", steps: [{ id: "s1", page: "nav" }, { id: "s2", page: "home" }] },
    ] } },
    { id: "home", parentId: "web", name: "Úvod", purpose: "", kind: "node", x: 0, y: 0, site: { kind: "page", path: "/" } },
  ],
  edges: [{ id: "e1", source: "home", target: "web" }],
};

describe("studio facts", () => {
  it("collects cards with an active lease or a running assistant session, anywhere in the project", () => {
    const status = normalizeWorkStatus({
      domains: [{ id: "web", worktrees: [{ id: "w1", state: "running", sessions: [
        { source: "lease", id: "a", state: "active", nodeId: "c1" }, { source: "lease", id: "b", state: "expired", nodeId: "c2" },
      ] }] }],
      unassigned: [{ id: "w2", sessions: [{ source: "assistant", id: "c", state: "running", nodeId: "c3" }] }],
      mainSessions: [{ source: "assistant", id: "d", state: "waiting", nodeId: "c4" }, { source: "lease", id: "e", state: "active", nodeId: "c5" }],
    });
    expect([...buildingNodes(status)].sort()).toEqual(["c1", "c3", "c5"]);
    expect(buildingNodes(null).size).toBe(0);
  });

  it("files findings by node, edge source and the domain of a journey", () => {
    const holes = holesByNode({ findings: [
      { rule: "page.no-goal", nodeId: "home", message: "bez cíle" },
      { rule: "edge.carries-unset", edgeId: "e1", message: "bez druhu" },
      { rule: "journey.unverified", journeyId: "j1", message: "neověřeno" },
      { rule: "journey.broken", journeyId: "gone", message: "nikde" },
    ] }, graph);
    expect(Object.fromEntries(holes)).toEqual({ home: ["bez cíle", "bez druhu"], web: ["neověřeno"] });
  });

  it("lists journeys with their step pages (without the menu) and their derivation", () => {
    const derived = [{ applicationId: "web", id: "j1", missing: [], segments: [] }];
    const [journey] = studioJourneys(graph, derived);
    expect(journey).toMatchObject({ id: "j1", name: "Kampaň", domainId: "web", derived: derived[0] });
    expect([...journey.pages]).toEqual(["home"]);
  });
});
