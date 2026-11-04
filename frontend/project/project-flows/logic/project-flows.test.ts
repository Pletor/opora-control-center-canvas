import { expect, it, vi } from "vitest";

vi.mock("@/shared/types/logic/types", () => ({ api: vi.fn() }));
const { copiesByNode, projectFlow } = await import("./project-flows");

const wf = (id: string, project_id: string | null, owner_ref: string, kind = "library_flow") => ({ id, kind, project_id, name: id, owner_ref });

it("finds adopted copies of a project by the node in owner_ref", () => {
  const byNode = copiesByNode([wf("lib", null, "opora:library:human:ai-rag/rag"), wf("a", "p", "opora:project-flow:web"), wf("b", "p", "opora:project-flow:web"),
    wf("c", "p", "opora:project-flow:kontakt"), wf("x", "other", "opora:project-flow:web"), wf("i", "p", "opora:page:web", "page_intent")], "p");
  expect([...byNode].map(([node, flows]) => [node, flows.map((flow) => flow.id)])).toEqual([["web", ["a", "b"]], ["kontakt", ["c"]]]);
});

it("says where the copy comes from and that the library has a newer version", () => {
  const source = { title: "RAG", activeN: 2, versions: [{ id: "v1", n: 1 }, { id: "v2", n: 2 }] } as never;
  expect(projectFlow({ id: "a", title: "RAG", derivedFrom: { workflowId: "lib", versionId: "v1" } }, source)).toEqual({
    id: "a", name: "RAG", from: "vychází z RAG@v1", newer: "v knihovně je novější v2" });
});
