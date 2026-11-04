import { expect, it } from "vitest";
import { flowCount, flowFacts, folderTags, tagsDescription } from "./library-shelf";

const flow = { id: "w", slug: "rag", title: "RAG", description: null, ownerRef: "opora:library:human:ai-rag/rag", projectId: null, activeVersionId: "v", activeN: 2, derivedCount: 3 };

it("reads tags from the folder description and writes them back", () => {
  expect(folderTags("Ukládání a dotazy #rag #Vektory #rag, bez#tagu")).toEqual(["rag", "vektory"]);
  expect(tagsDescription("rag, #Vektory  embedding rag")).toBe("#rag #vektory #embedding");
  expect(tagsDescription("  ")).toBe("");
});

it("counts flows and tells the active version and derived items", () => {
  expect(flowCount({ id: "f", owner: "human", slug: "ai-rag", title: "AI a RAG", description: "", order: 0, flows: [flow, flow] })).toBe("2 plátna");
  expect(flowFacts(flow)).toBe("aktivní v2 · 3 odvozené");
  expect(flowFacts({ ...flow, activeN: null, derivedCount: 0 })).toBe("bez aktivní verze");
});
