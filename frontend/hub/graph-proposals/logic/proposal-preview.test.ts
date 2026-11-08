import { describe, expect, it } from "vitest";
import { proposalFocus, proposalPreview, scopedProposalLink } from "./proposal-preview";
import type { GraphProposal } from "./graph-proposals";
import type { Graph } from "@/shared/types/logic/types";

const graph = (id: string): Graph => ({ nodes: [{ id, name: id, purpose: "", kind: "node", parentId: null, x: 0, y: 0 }], edges: [] });
describe("saved proposal canvas projection", () => {
  it("focuses additions over a large base without dropping the full graph", () => {
    const base = { nodes: Array.from({ length: 185 }, (_, i) => graph(`base-${i}`).nodes[0]), edges: [] };
    const p = { baseGraph: base, additions: graph("new") } as unknown as GraphProposal;
    expect(proposalFocus(p)).toEqual([{ id: "new" }]);
    expect(proposalPreview(p)?.nodes).toHaveLength(186);
  });
  it("focuses surviving changed nodes and falls back to all for removal-only", () => {
    const p = { schemaVersion: 2, additions: { nodes: [], edges: [] }, resultGraph: graph("changed"),
      changes: { nodes: [{ id: "removed", operation: "remove" }, { id: "changed", operation: "update" }], edges: [] } } as unknown as GraphProposal;
    expect(proposalFocus(p)).toEqual([{ id: "changed" }]);
    expect(proposalFocus({ ...p, resultGraph: graph("other") })).toBeUndefined();
  });
  it("uses real v1 IDs and existing endpoints, without mutating the accepted base", () => {
    const base = graph("existing"), addition = graph("uuid-added");
    addition.edges.push({ id: "edge-real", source: "existing", target: "uuid-added", port: "next" });
    const p = { baseGraph: base, additions: addition, refs: { task: "uuid-added" } } as unknown as GraphProposal;
    const before = JSON.stringify(p);
    expect(proposalPreview(p)).toEqual({ nodes: [...base.nodes, ...addition.nodes], edges: addition.edges });
    expect(JSON.stringify(p)).toBe(before);
  });
  it("uses server proposed working v2 result, never accepted result or client edit replay", () => {
    const p = { schemaVersion: 2, baseGraph: graph("base"), additions: graph("addition"),
      acceptedResultGraph: graph("accepted"), resultGraph: graph("working-result") } as GraphProposal;
    expect(proposalPreview(p)).toBe(p.resultGraph);
    expect(proposalPreview({ ...p, resultGraph: undefined })).toBeNull();
  });
  it("restores only the proposal linked to the exact project/workspace", () => {
    expect(scopedProposalLink("?project=p&workspace=w&ohGraph=abc-123", "p", "w")).toBe("abc-123");
    expect(scopedProposalLink("?project=p&workspace=other&ohGraph=abc", "p", "w")).toBe("");
    expect(scopedProposalLink("?project=other&workspace=w&ohGraph=abc", "p", "w")).toBe("");
    expect(scopedProposalLink("?project=p&workspace=w&ohGraph=../bad", "p", "w")).toBe("");
  });
});
