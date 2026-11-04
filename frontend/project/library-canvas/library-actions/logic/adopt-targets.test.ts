import { expect, it, vi } from "vitest";

vi.mock("@/shared/types/logic/types", () => ({ api: vi.fn() }));
const { adoptTargets, viewWorkspace } = await import("./adopt-targets");

it("offers domains first, then pages, and reads local projects from the draft workspace", () => {
  const graph = { nodes: [
    { id: "page", name: "Kontakt", site: { kind: "page", path: "/kontakt" } },
    { id: "web", name: "Web", site: { kind: "application", environments: [{ name: "Produkce", host: "www.example.cz" }] } },
    { id: "box", name: "Box" },
  ], edges: [] } as never;
  expect(adoptTargets(graph)).toEqual([{ id: "web", label: "Doména · Produkce · www.example.cz" }, { id: "page", label: "Stránka · Kontakt (/kontakt)" }]);
  expect(viewWorkspace({ id: "p", name: "P", url: null, branch: null, sourceKind: "local" })).toBe("draft");
  expect(viewWorkspace({ id: "p", name: "P", url: "https://x", branch: "main", sourceKind: "github" })).toBe("main");
});
