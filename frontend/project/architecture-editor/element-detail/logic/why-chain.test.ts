import { describe, expect, it } from "vitest";
import type { CanvasNode, CustomerJourney, Graph } from "@/shared/types/logic/types";
import { whyChain, whyChainText } from "./why-chain";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({
  id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, ...extra,
});
const sections = [
  { id: "hero", role: "hero" as const, name: "Hlavička", intent: "" },
  { id: "form", role: "form" as const, name: "Poptávka", intent: "Jméno a e-mail", moves: "Rozptýlí obavu ze spamu." },
];
const journeys: CustomerJourney[] = [
  { id: "blog", name: "Blog", pointB: "Čte dál.", steps: [{ id: "a", page: "nav" }, { id: "b", page: "blog" }] },
  { id: "poptavka", name: "Poptávka", pointB: "Má plán a termín.", steps: [
    { id: "vstup", page: "nav" }, { id: "kontakt", page: "page", shift: "Chce prohlídku." },
    { id: "znovu", page: "page", shift: "Druhý krok se nebere." }] },
];
const graph = (appJourneys: CustomerJourney[] | null = journeys): Graph => ({
  nodes: [
    { ...node("app", null), kind: "sector", site: { kind: "application", environments: [], ...(appJourneys ? { journeys: appJourneys } : {}) } },
    node("page", "app", { site: { kind: "page", path: "/kontakt", sections } }),
    node("ui", "page"),
    node("field", "ui", { card: { section: "form" } }),
    node("hero", "page", { card: { section: "hero" } }),
    node("stale", "page", { card: { section: "smazana" } }),
    node("loose", null, { card: { section: "form" } }),
    { ...node("sector", "page"), kind: "sector" },
  ],
  edges: [],
});

describe("řetěz „proč“ u komponenty", () => {
  it("spojí bod B první cesty se stránkou, posun jejího prvního kroku a moves sekce komponenty", () => {
    const chain = whyChain(graph(), "field");
    expect(chain).toEqual({ journey: "Poptávka", pointB: "Má plán a termín.", shift: "Chce prohlídku.", moves: "Rozptýlí obavu ze spamu." });
    expect(whyChainText(chain!)).toBe("B: Má plán a termín. → stránka: Chce prohlídku. → sekce: Rozptýlí obavu ze spamu.");
  });
  it("chybějící článek vynechá a nic nedoplní", () => {
    expect(whyChain(graph(), "hero")).toEqual({ journey: "Poptávka", pointB: "Má plán a termín.", shift: "Chce prohlídku.", moves: null });
    expect(whyChain(graph(), "stale")?.moves).toBeNull();
    const offJourney = whyChain(graph(null), "field");
    expect(offJourney).toEqual({ journey: null, pointB: null, shift: null, moves: "Rozptýlí obavu ze spamu." });
    expect(whyChainText(offJourney!)).toBe("sekce: Rozptýlí obavu ze spamu.");
  });
  it("bez bodu B, posunu i moves, mimo stránku, u sektoru a u stránky samé nevrací nic", () => {
    expect(whyChain(graph(null), "hero")).toBeNull();
    expect(whyChain(graph(), "loose")).toBeNull();
    expect(whyChain(graph(), "sector")).toBeNull();
    expect(whyChain(graph(), "page")).toBeNull();
    expect(whyChain(graph(), "nic")).toBeNull();
  });
});
