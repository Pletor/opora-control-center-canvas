import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { parseSection, sectionChoice } from "./section-choice";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({
  id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, ...extra,
});
const sections = [
  { id: "hero", role: "hero" as const, name: "Hlavička", intent: "" },
  { id: "form", role: "cta" as const, name: "Poptávka", intent: "Jméno a e-mail" },
];
const graph: Graph = {
  nodes: [
    { ...node("app", null), kind: "sector", site: { kind: "application", environments: [] } },
    node("page", "app", { site: { kind: "page", path: "/kontakt", sections } }),
    node("bare", "app", { site: { kind: "page", path: "/o-nas" } }),
    node("ui", "page"),
    node("field", "ui", { card: { layer: "frontend", section: "form" } }),
    node("stale", "page", { card: { section: "smazana" } }),
    node("plain", "bare"),
    node("lost", "bare", { card: { section: "hero" } }),
    node("loose", null),
    { ...node("sector", "page"), kind: "sector" },
  ],
  edges: [],
};

describe("výběr sekce stránky", () => {
  it("nabídne sekce nejbližší stránky s rolí a názvem, neurčeno je prázdná hodnota", () => {
    expect(sectionChoice(graph, "ui")).toEqual({
      options: [{ id: "hero", label: "Úvod · Hlavička" }, { id: "form", label: "Výzva · Poptávka" }],
      value: "",
      missing: null,
    });
    expect(sectionChoice(graph, "field")).toMatchObject({ value: "form", missing: null });
  });
  it("odkaz na sekci, kterou stránka nemá, ukáže jako chybějící", () => {
    expect(sectionChoice(graph, "stale")).toMatchObject({ value: "smazana", missing: "smazana" });
    expect(sectionChoice(graph, "lost")).toEqual({ options: [], value: "hero", missing: "hero" });
  });
  it("bez sekcí, mimo stránku, u stránky samé a u sektoru se výběr neukáže", () => {
    for (const id of ["plain", "loose", "page", "sector", "app", "nic"]) expect(sectionChoice(graph, id)).toBeNull();
  });
  it("prázdná volba znamená neurčeno", () => {
    expect(parseSection("")).toBeNull();
    expect(parseSection("form")).toBe("form");
  });
});
