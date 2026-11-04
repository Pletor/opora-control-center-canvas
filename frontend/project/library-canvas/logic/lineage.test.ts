import { expect, it } from "vitest";
import { lineageOf } from "./lineage";

const source = { title: "RAG – ingest a dotaz", activeN: 3, versions: [{ id: "v1", n: 1 }, { id: "v3", n: 3 }] };

it("tells where a flow comes from, that the source has a newer version and who derives from it", () => {
  expect(lineageOf({ derivedFrom: { workflowId: "w", versionId: "v1" } }, source)).toEqual({
    from: "vychází z RAG – ingest a dotaz@v1", newer: "v knihovně je novější v3", derived: null });
  expect(lineageOf({ derivedFrom: { workflowId: "w", versionId: "v3" } }, source).newer).toBeNull();
  expect(lineageOf({ derivedFrom: { workflowId: "w", versionId: "v1" } }, null).from).toBe("vychází z prvku, který už v knihovně není");
  expect(lineageOf({ derivedFrom: null, derived: [{ projectId: "p1" }] }, null, (id) => id === "p1" ? "Ample" : id).derived).toBe("odvozené: 1 · v projektech: Ample");
  expect(lineageOf({ derivedFrom: null, derived: [{ projectId: "ample" }, { projectId: null }, { projectId: "ample" }] }, null)).toEqual({
    from: null, newer: null, derived: "odvozené: 3 · v projektech: ample" });
});
