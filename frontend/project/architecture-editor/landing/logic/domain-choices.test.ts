import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { domainChoices, domainLabel } from "./domain-choices";

const app = (id: string, environments: { name: string; host: string }[]) => ({ id, name: id, purpose: "", kind: "sector", parentId: null, x: 0, y: 0, site: { kind: "application", environments } }) as unknown as CanvasNode;
const graph: Graph = { nodes: [
  app("dev-www", [{ name: "Vývoj", host: "www.example.dev" }]),
  app("prod-app", [{ name: "Produkce", host: "app.example.cz" }]),
  app("legacy", [{ name: "Produkce", host: "a.cz" }, { name: "Vývoj", host: "a.dev" }]),
  app("prod-www", [{ name: "Produkce", host: "www.example.cz" }]),
  { ...app("page", []), site: { kind: "page", path: "/" } } as unknown as CanvasNode,
], edges: [] };

describe("domain choices", () => {
  it("lists single-host domains, Production first, then by host", () => {
    expect(domainChoices(graph)).toEqual([
      { id: "prod-app", label: "Produkce · app.example.cz" },
      { id: "prod-www", label: "Produkce · www.example.cz" },
      { id: "dev-www", label: "Vývoj · www.example.dev" },
    ]);
  });

  it("labels unknown domains by ID", () => {
    const choices = domainChoices(graph);
    expect(domainLabel(choices, "prod-app")).toBe("Produkce · app.example.cz");
    expect(domainLabel(choices, "project")).toBe("project");
    expect(domainLabel(choices, "")).toBe("bez domény");
  });
});
