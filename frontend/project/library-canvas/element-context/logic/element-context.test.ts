import { expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { elementContext, logicCanvasTitle, planRoute } from "./element-context";

const node = (id: string, parentId: string | null, extra: object = {}) => ({ id, parentId, kind: "node", name: id[0].toUpperCase() + id.slice(1), purpose: "", x: 0, y: 0, ...extra });
const graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
  node("kurz", "web", { site: { kind: "page", path: "/kurz", sections: [{ id: "cta", role: "cta", name: "Výzva", intent: "" }] } }),
  node("koupit", "kurz", { element: { kind: "action" }, card: { section: "cta" } }),
  node("clen", "kurz", { element: { kind: "actor" } }),
  node("stara", "kurz"),
], edges: [] } as unknown as Graph;

it("tells the element kind, name, page › box and domain of a logic flow", () => {
  expect(elementContext(graph, "koupit")).toEqual({ nodeId: "koupit", kind: "Akce", name: "Koupit", pageId: "kurz", page: "Kurz", box: "Výzva", domainId: "web" });
  expect(elementContext(graph, "clen")?.box).toBeNull();
  expect(elementContext(graph, "stara")).toBeNull();
  expect(elementContext(graph, "nic")).toBeNull();
});

it("titles the canvas as logic and data flow of the element", () => {
  expect(logicCanvasTitle(elementContext(graph, "koupit")!)).toBe("Logika a tok dat · Koupit");
});

it("returns to the page plan with the element selected and a fresh editor identity", () => {
  const route = planRoute("?project=p&workspace=w&projectView=library&flow=f&editorId=old&domainId=x", elementContext(graph, "koupit")!);
  expect(Object.fromEntries(route)).toEqual({ project: "p", workspace: "w", projectView: "architecture", domainId: "web", pageId: "kurz", architectureNode: "koupit" });
});
