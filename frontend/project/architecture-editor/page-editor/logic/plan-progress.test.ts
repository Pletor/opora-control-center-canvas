import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph, GraphEdge } from "@/shared/types/logic/types";
import type { StudioState } from "@/project/studio/logic/studio-status";
import { elementMilestones, nextAdmissible, pageComplete, pageElements } from "./plan-progress";

const node = (id: string, parentId: string | null, kind: CanvasNode["kind"] = "node", extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, parentId, kind, name: id.toUpperCase(), purpose: "", x: 0, y: 0, ...extra });
const requires = (source: string, target: string): GraphEdge => ({ id: source + target, source, target, relation: "requires" });
const states = (entries: Record<string, StudioState>) => new Map(Object.entries(entries).map(([id, state]) => [id, { state }]));
const page = node("p", "d", "sector", { site: { kind: "page", path: "/p" } });
const graph = (edges: GraphEdge[] = []): Graph => ({ nodes: [node("d", null, "sector"), page, node("a", "p", "node", { element: { kind: "action" } }),
  node("old", "p", "sector"), node("b", "p", "node", { element: { kind: "actor" } }), node("plain", "p"),
  node("sub", "p", "sector", { site: { kind: "page", path: "/p/sub" } }), node("area", "p", "area"), node("note", "p", "comment"), node("deep", "a")], edges });

describe("elementMilestones", () => {
  const steps = (state?: StudioState) => elementMilestones(state).map((item) => item.step);
  it("plán a díra jsou v Návrhu", () => {
    expect(steps("plan")).toEqual(["now", "wait", "wait"]);
    expect(steps("hole")).toEqual(["now", "wait", "wait"]);
    expect(steps(undefined)).toEqual(["now", "wait", "wait"]);
  });
  it("stavba, hotovo a ověřeno posouvají milníky", () => {
    expect(steps("building")).toEqual(["done", "now", "wait"]);
    expect(steps("done")).toEqual(["done", "done", "now"]);
    expect(steps("verified")).toEqual(["done", "done", "done"]);
    expect(elementMilestones("plan").map((item) => item.label)).toEqual(["Návrh", "Realizace", "Ověření"]);
  });
});

describe("pageElements", () => {
  it("bere jen přímé prvky logiky, ne starší sektory a komponenty, podstránky, oblasti, komentáře ani vnuky", () => {
    expect(pageElements(graph(), "p").map((item) => item.id)).toEqual(["a", "b"]);
  });
});

describe("pageComplete", () => {
  it("stránka bez prvků kompletní není", () => {
    expect(pageComplete({ nodes: [page], edges: [] }, "p", new Map())).toBe(false);
  });
  it("kompletní jen když jsou všechny prvky ověřené", () => {
    expect(pageComplete(graph(), "p", states({ a: "verified", b: "done" }))).toBe(false);
    expect(pageComplete(graph(), "p", states({ a: "verified", b: "verified" }))).toBe(true);
  });
});

describe("nextAdmissible", () => {
  it("bez prvků je prázdno, se všemi ověřenými hotovo", () => {
    expect(nextAdmissible({ nodes: [page], edges: [] }, "p", new Map())).toEqual({ kind: "empty" });
    expect(nextAdmissible(graph(), "p", states({ a: "verified", b: "verified" }))).toEqual({ kind: "verified" });
  });
  it("vezme první neověřený prvek v pořadí grafu", () => {
    const next = nextAdmissible(graph(), "p", states({ a: "verified" }));
    expect(next.kind === "step" && next.node.id).toBe("b");
  });
  it("zdroj requires čeká, dokud cíl není aspoň hotový", () => {
    const edges = [requires("a", "b")];
    const waiting = nextAdmissible(graph(edges), "p", states({ a: "plan", b: "building" }));
    expect(waiting.kind === "step" && waiting.node.id).toBe("b");
    const free = nextAdmissible(graph(edges), "p", states({ a: "plan", b: "done" }));
    expect(free.kind === "step" && free.node.id).toBe("a");
  });
  it("cíl requires není blokovaný svým zdrojem (směr vazby)", () => {
    const next = nextAdmissible(graph([requires("b", "a")]), "p", states({ a: "plan", b: "plan" }));
    expect(next.kind === "step" && next.node.id).toBe("a");
  });
  it("když nic není přípustné, řekne, na který vstup se čeká", () => {
    const next = nextAdmissible(graph([requires("a", "x"), requires("b", "x")]), "p", states({}));
    expect(next).toMatchObject({ kind: "waiting", node: { id: "a" }, inputs: ["x"] });
  });
  it("ostatní významy vazeb neblokují", () => {
    const next = nextAdmissible(graph([{ id: "u", source: "a", target: "b", relation: "uses" }]), "p", states({}));
    expect(next.kind === "step" && next.node.id).toBe("a");
  });
});
