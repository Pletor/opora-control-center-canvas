import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { cardAddress, cardLayer, cardPath, effectiveStatus, effectiveType, formatPath, normalizeCard, slug, withCard } from "./card-context";

const node = (id: string, name: string, parentId: string | null = null, extra: Partial<CanvasNode> = {}): CanvasNode => ({
  id, parentId, kind: "node", name, purpose: "", x: 0, y: 0, ...extra,
});

// Případy jsou tytéž jako v backend/canvas/test_card_context.py, aby obě strany počítaly stejně.
describe("effectiveType", () => {
  it.each([
    ["[research] Trh", "research"],
    ["[prototype] Náčrt", "prototype"],
    ["[grilling] Otázky", "grilling"],
    ["[task] Router", "task"],
    ["[Task] Router", null],
    ["[task]Router", null],
    [" [task] Router", null],
    ["[bug] Router", null],
    ["Router [task] ", null],
    ["Router", null],
  ])("%s → %s", (name, expected) => {
    expect(effectiveType(node("n1", name))).toBe(expected);
  });

  it("typ je jen z předpony, vrstva jen z karty", () => {
    expect(effectiveType(node("n1", "[task] Router", null, { card: { layer: "backend" } }))).toBe("task");
    expect(effectiveType(node("n1", "Router", null, { card: { status: "ready" } }))).toBeNull();
    expect(cardLayer(node("n1", "Router", null, { card: { layer: "backend" } }))).toBe("backend");
    expect(cardLayer(node("n1", "Router", null, { card: { layer: "fe" as never } }))).toBeNull();
    expect(cardLayer(node("n1", "Router"))).toBeNull();
  });
});

describe("effectiveStatus", () => {
  it("done jen z uzavření, jinak ruční stav, jinak null", () => {
    expect(effectiveStatus(node("n1", "A"), false)).toBeNull();
    expect(effectiveStatus(node("n1", "A", null, { card: { status: "draft" } }), false)).toBe("draft");
    expect(effectiveStatus(node("n1", "A", null, { card: { status: "ready" } }), true)).toBe("done");
    expect(effectiveStatus(node("n1", "A"), true)).toBe("done");
  });
});

describe("slug", () => {
  it.each([
    ["Pop-up tvorby", "pop-up-tvorby"],
    ["Žluťoučký kůň", "zlutoucky-kun"],
    ["[task] Router API", "router-api"],
    ["  --Editor!!  ", "editor"],
    ["A__B  C", "a-b-c"],
    ["!!!", "n1"],
    ["", "n1"],
    ["[task] ", "n1"],
  ])("%s → %s", (name, expected) => {
    expect(slug(name, "n1")).toBe(expected);
  });
});

describe("cardPath a cardAddress", () => {
  const nodes = [
    node("s1", "Editor", null, { kind: "sector" }),
    node("n1", "[task] Pop-up tvorby", "s1"),
  ];

  it("jdou od kořene ke kartě", () => {
    expect(cardPath(nodes, nodes[1])).toEqual(["Editor", "[task] Pop-up tvorby"]);
    expect(formatPath(cardPath(nodes, nodes[1]))).toBe("Editor › [task] Pop-up tvorby");
    expect(cardAddress(nodes, nodes[1])).toBe("editor/pop-up-tvorby");
    expect(cardAddress(nodes, nodes[0])).toBe("editor");
  });

  it("přežijí chybějícího rodiče i kruh v datech", () => {
    const lonely = node("n1", "Sám", "zmizel");
    expect(cardAddress([lonely], lonely)).toBe("sam");
    const a = node("a", "A", "b");
    const b = node("b", "B", "a");
    expect(cardAddress([a, b], a)).toBe("b/a");
  });
});

describe("normalizeCard a withCard", () => {
  it("prázdné a neplatné klíče vypustí, prázdná karta je undefined", () => {
    expect(normalizeCard({ layer: "", status: "", due: "", model: "", effort: "" })).toBeUndefined();
    expect(normalizeCard({ layer: "database", due: "2026-10-10", effort: "bad" })).toEqual({ layer: "database", due: "2026-10-10" });
    expect(normalizeCard({ layer: "task" })).toBeUndefined();
    expect(normalizeCard(undefined)).toBeUndefined();
  });

  it("prázdná karta klíč card odstraní, jinak ostatní pole nechá být", () => {
    const old = node("n1", "A", null, { card: { layer: "frontend" }, purpose: "p" });
    expect("card" in withCard(old, { layer: "" })).toBe(false);
    expect(withCard(old, { status: "ready" })).toEqual({ ...old, card: { status: "ready" } });
    expect(withCard(node("n2", "B"), {})).toEqual(node("n2", "B"));
  });
});
