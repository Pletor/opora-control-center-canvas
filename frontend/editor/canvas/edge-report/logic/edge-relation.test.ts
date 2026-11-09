import { expect, it } from "vitest";
import { withEdgeRelation } from "./edge-relation";

it("changes meaning while preserving edge identity, visual port and data flow", () => {
  const edge = { id: "stable", source: "ui", target: "api", port: "next" as const, carries: "command" as const };
  const changed = withEdgeRelation(edge, "requires", "  Accepted API contract  ");
  expect(changed).toEqual({ ...edge, relation: "requires", reason: "Accepted API contract" });
  expect(withEdgeRelation(changed, "", "ignored")).toEqual(edge);
  expect(edge).not.toHaveProperty("relation");
});

it("preserves block source handles and omits blank explanation", () => {
  const edge = { id: "block_edge", source: "a", target: "b", port: "block" as const, sourceBlockId: "blk", sourcePortId: "output" };
  expect(withEdgeRelation(edge, "evidences", " ")).toEqual({ ...edge, relation: "evidences" });
});

it("preserves pinned input readiness only on blocking dependency", () => {
  const edge = { id: "required", source: "a", target: "b", relation: "requires" as const,
    requirement: { readiness: "implemented" as const, revision: 3 } };
  expect(withEdgeRelation(edge, "requires", "").requirement).toEqual(edge.requirement);
  expect(withEdgeRelation(edge, "uses", "")).not.toHaveProperty("requirement");
  expect(withEdgeRelation(edge, "", "")).not.toHaveProperty("requirement");
});
