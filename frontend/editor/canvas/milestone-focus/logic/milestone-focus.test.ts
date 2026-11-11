import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import type { Node } from "@xyflow/react";
import type { IntakeResponse } from "@/editor/control-tower/intake-plan/logic/intake-plan";
import { activeMilestones, focusMilestoneNodes, milestoneMembers } from "./milestone-focus";

function graph(): Graph {
  const node = (id: string, parentId: string | null) => ({ id, parentId, kind: "node" as const, name: id, purpose: "", x: 0, y: 0 });
  return { nodes: [node("ui", null), node("identity", null), node("data", null), node("other", null),
    node("login", "ui"), node("profile", "ui"), node("token", "identity"), node("tenant", "data"), node("input", "login")], edges: [] };
}

describe("milestone focus across the structure", () => {
  it("keeps sibling branches and their navigation paths relevant without including unrelated siblings", () => {
    const members = milestoneMembers(graph(), ["login", "token", "tenant"]);
    expect([...members].sort()).toEqual(["ui", "identity", "data", "login", "token", "tenant", "input"].sort());
    expect(members.has("profile")).toBe(false);
    expect(members.has("other")).toBe(false);
  });

  it("uses stable IDs after rename and move, ignores missing references and terminates cycles", () => {
    const moved = graph();
    Object.assign(moved.nodes.find(node => node.id === "login")!, { name: "Renamed", parentId: "identity" });
    moved.nodes.push({ ...moved.nodes[0], id: "loop-a", parentId: "loop-b" },
      { ...moved.nodes[0], id: "loop-b", parentId: "loop-a" });
    expect([...milestoneMembers(moved, ["login", "missing", "loop-a"])].sort())
      .toEqual(["identity", "login", "input", "loop-a", "loop-b"].sort());
  });

  it("preserves access, selection, positions and independent tag dimming", () => {
    const nodes: Node[] = ["login", "token", "profile"].map(id => ({ id, type: "canvas", position: { x: 5, y: 8 },
      selected: id === "profile", data: { dimmed: id === "token" } }));
    const focused = focusMilestoneNodes(nodes, new Set(["login", "token"]));
    expect(focused.map(node => [node.id, node.position, node.selected])).toEqual(nodes.map(node => [node.id, node.position, node.selected]));
    expect(focused.map(node => node.hidden)).toEqual([undefined, undefined, undefined]);
    expect(focused.map(node => node.data.dimmed)).toEqual([false, true, true]);
    expect(nodes[2].data.dimmed).toBe(false);
    expect(focusMilestoneNodes(nodes, null)).toBe(nodes);
  });

  it("shows only existing active milestones and never turns closed cards into integration evidence", () => {
    const data: IntakeResponse = { areas: [{ id: "area", name: "Entry", proposed: [], requirements: [], deferred: [],
      milestone: { id: "m", title: "Functional login", status: "active", done: true, progress: 100,
        criteria: [{ id: "c", text: "Prototype approved", done: true, cards: ["login", { id: "login", done: true }, "token"] }] } }],
      unassigned: [], entries: [], pending: 0, duplicates: 0 };
    expect(activeMilestones(data)).toEqual([{ id: "m", title: "Functional login", area: "Entry", areaId: "area", cards: ["login", "token"], closure: 100 }]);
    expect(activeMilestones(data)[0]).not.toHaveProperty("verified");
    data.areas[0].milestone!.status = "proposed";
    expect(activeMilestones(data)).toEqual([]);
    expect(activeMilestones(null)).toEqual([]);
  });
});
