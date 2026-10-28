import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { MAP_CHECK_RULES, MAP_CHECK_TEXT, mapCheckGroups, mapCheckTarget, mapCheckUrl, normalizeMapCheck } from "./map-check";

const node = (id: string, parentId: string | null, site?: object) => ({ id, parentId, name: id, purpose: "", ...(site ? { site } : {}) }) as unknown as CanvasNode;
const app = node("app", null, { kind: "application", environments: [{ name: "Prod", host: "a.cz" }], journeys: [{ id: "kurz", name: "Kurz", steps: [] }] });
const graph = { nodes: [app, node("home", "app", { kind: "page", path: "/" }), node("form", "home"), node("btn", "form"), node("loose", "app"),
  node("other", null, { kind: "application", environments: [] }), node("cizi", "other", { kind: "page", path: "/" })],
  edges: [{ id: "e1", source: "btn", target: "form" }, { id: "e2", source: "loose", target: "btn" }] } as unknown as Graph;

describe("kontrola mapy na mapě domény", () => {
  it("adresa dotazu nese projekt", () => {
    expect(mapCheckUrl("p 1")).toBe("/api/project-architecture/map-check?project=p+1");
    expect(mapCheckUrl("p 1", true)).toBe("/api/project-architecture/map-check?project=p+1&locate=1");
  });
  it("čte nálezy a neznámá pravidla, nálezy bez zprávy i cizí tvary zahodí", () => {
    const raw = { findings: [{ rule: "page.no-goal", nodeId: "home", message: "Stránka nemá cíl (goal)." }, { rule: "journey.broken", journeyId: "kurz", edgeId: 3, message: "Cesta Kurz: chybí." },
      { rule: "neznámé", nodeId: "x", message: "m" }, { rule: "page.no-goal", nodeId: "x" }, null, "x"], summary: { "page.no-goal": 1 } };
    expect(normalizeMapCheck(raw)).toEqual({ findings: [{ rule: "page.no-goal", nodeId: "home", message: "Stránka nemá cíl (goal)." },
      { rule: "journey.broken", journeyId: "kurz", message: "Cesta Kurz: chybí." }] });
    expect(normalizeMapCheck({ findings: [{ rule: "journey.unrealized", journeyId: "j", solverId: "p", message: "m" }] }).findings[0].solverId).toBe("p");
    expect(normalizeMapCheck(null)).toEqual({ findings: [] });
    expect(normalizeMapCheck({ findings: "x" })).toEqual({ findings: [] });
  });
  it("každé pravidlo má český popisek a radu", () => {
    for (const rule of MAP_CHECK_RULES) expect(MAP_CHECK_TEXT[rule].label && MAP_CHECK_TEXT[rule].advice).toBeTruthy();
    expect(MAP_CHECK_TEXT["page.no-goal"].label).toBe("Stránka nemá cíl");
  });
  it("klik vede na stránku, na nejbližší stránku komponenty, na cestu a na stránku zdroje hrany", () => {
    expect(mapCheckTarget({ rule: "page.no-goal", nodeId: "home", message: "m" }, graph)).toEqual({ kind: "page", id: "home" });
    expect(mapCheckTarget({ rule: "state.no-error", nodeId: "btn", message: "m" }, graph)).toEqual({ kind: "node", id: "btn", pageId: "home" });
    expect(mapCheckTarget({ rule: "journey.broken", journeyId: "kurz", message: "m" }, graph)).toEqual({ kind: "journey", id: "kurz" });
    expect(mapCheckTarget({ rule: "edge.carries-unset", edgeId: "e1", message: "m" }, graph)).toEqual({ kind: "edge", id: "e1", pageId: "home", sourceId: "btn" });
    expect(mapCheckTarget({ rule: "section.unknown", nodeId: "loose", message: "m" }, graph)).toBeNull();
    expect(mapCheckTarget({ rule: "state.no-error", nodeId: "pryc", message: "m" }, graph)).toBeNull();
    expect(mapCheckTarget({ rule: "edge.carries-unset", edgeId: "e9", message: "m" }, graph)).toBeNull();
  });
  it("seskupí nálezy jedné domény v pořadí pravidel a cizí doménu vynechá", () => {
    const check = normalizeMapCheck({ findings: [
      { rule: "edge.carries-unset", edgeId: "e1", message: "hrana" }, { rule: "page.no-goal", nodeId: "home", message: "home" },
      { rule: "page.no-goal", nodeId: "cizi", message: "cizí" }, { rule: "journey.broken", journeyId: "kurz", message: "cesta" },
      { rule: "journey.unrealized", journeyId: "jinde", message: "jinde" }, { rule: "section.unknown", nodeId: "loose", message: "volná" }] });
    const groups = mapCheckGroups(check, graph, app);
    expect(groups.map((group) => [group.rule, group.items.map((item) => item.finding.message)])).toEqual([
      ["journey.broken", ["cesta"]], ["page.no-goal", ["home"]], ["section.unknown", ["volná"]], ["edge.carries-unset", ["hrana"]]]);
    expect(groups[0].label).toBe(MAP_CHECK_TEXT["journey.broken"].label);
    expect(groups[2].items[0].target).toBeNull();
    // Místo rozliší stejné zprávy: název uzlu, cesty, nebo zdroj → cíl vazby.
    expect(groups.map((group) => group.items[0].place)).toEqual(["Kurz", "home", "loose", "btn → form"]);
    expect(mapCheckGroups({ findings: [] }, graph, app)).toEqual([]);
  });
});
