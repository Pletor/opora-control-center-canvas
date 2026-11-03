import { expect, it } from "vitest";
import type { FlowGraph, FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { diffCounts, diffText, diffToActive, intentLane, pickIntentVersion } from "./intent-versions";

const node = (id: string, shows = "") => ({ id, type: "intent.view", params: { shows } });
const version = (id: string, n: number, status: FlowVersion["status"], graph: FlowGraph = { nodes: [], edges: [] }): FlowVersion =>
  ({ id, workflow_id: "w", n, graph, hash: "h", parent_version_id: null, status, eval_run_id: null, created_at: "" });

it("puts the active version, the candidate and only a draft newer than both on the lane", () => {
  const lane = intentLane([version("a", 1, "active"), version("old", 2, "draft"), version("c", 3, "candidate"), version("r", 4, "retired")]);
  expect([lane.active?.id, lane.candidate?.id, lane.draft]).toEqual(["a", "c", null]);
  expect(intentLane([version("a", 1, "active"), version("d", 2, "draft")]).draft?.id).toBe("d");
  expect(intentLane([])).toEqual({ active: null, candidate: null, draft: null });
});

it("shows the chosen version, otherwise the candidate waiting for the human", () => {
  const versions = [version("a", 1, "active"), version("c", 2, "candidate")];
  const lane = intentLane(versions);
  expect(pickIntentVersion(versions, lane, "a")?.id).toBe("a");
  expect(pickIntentVersion(versions, lane, null)?.id).toBe("c");
  expect(pickIntentVersion([], intentLane([]), null)).toBeNull();
});

it("counts added, removed and changed nodes against the active version", () => {
  const active = version("a", 1, "active", { nodes: [node("entry"), node("view", "hero"), node("gone")], edges: [] });
  const candidate = version("c", 2, "candidate", { nodes: [node("entry"), node("view", "formulář"), node("done"), node("error")], edges: [] });
  const lane = intentLane([active, candidate]);
  const counts = diffCounts(diffToActive(lane, candidate, candidate.graph)!);
  expect(counts).toEqual({ added: 2, removed: 1, changed: 1 });
  expect(diffText(counts)).toBe("+2 přidáno · −1 odebráno · ~1 změněno");
  expect(diffToActive(lane, active, active.graph)).toBeNull();
  expect(diffCounts(diffToActive(intentLane([candidate]), candidate, candidate.graph)!).added).toBe(4);
});
