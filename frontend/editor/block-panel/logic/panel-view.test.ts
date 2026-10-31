import { describe, expect, it } from "vitest";
import { emptyBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { parseCardTrail } from "./card-trail";
import { cardLabel, panelView } from "./panel-view";

describe("panel-view", () => {
  const block = { ...emptyBlock(), number: "1", title: "Zápis metrik", text: "Každá odpověď zapíše metriky." };

  it("hlavička bloku a poslední změna karty (tool.use není změna)", () => {
    const trail = parseCardTrail({ nodeId: "n", judgment: [{ code: "missing_summary" }], recent: [
      { at: "2026-10-31T11:52:00", who: "office", label: "Edit", kind: "tool.use" },
      { at: "2026-10-31T11:51:00", who: "heart", label: "pořadí", kind: "write" }] });
    const view = panelView({ block, blocks: [block], cardId: "n", cardName: "Karta", card: null, trail, edges: [], now: new Date("2026-10-31T12:00:00") });
    expect(view.head).toMatchObject({ kind: "block", number: "1", id: block.id, title: "Zápis metrik", cardName: "Karta", order: null,
      change: { who: "Srdce", whoKind: "heart", when: "11:51", what: "pořadí" } });
    expect(view.judgmentViews.map((j) => j.label)).toEqual(["chybí shrnutí"]);
    expect(view.timeline.flatMap((g) => g.items)).toHaveLength(1);
  });

  it("bez stopy prázdná osa, porty i úsudek", () => {
    const empty = panelView({ block, blocks: [block], cardId: "n", cardName: "Karta", card: null, trail: null, edges: [] });
    expect([empty.timeline, empty.ports, empty.judgments, empty.head.change, empty.live]).toEqual([[], [], [], null, null]);
  });

  it("režim karty: bez bloku hlavička nese název a účel karty, porty jsou všechny vazby z karty", () => {
    const trail = parseCardTrail({ nodeId: "n", ports: [
      { edgeId: "e1", targetId: "t1", targetName: "API", summary: "Hotové API" },
      { edgeId: "e2", targetId: "t2", targetName: "Web", summary: "" }] });
    const edges = [{ id: "e1", source: "n", target: "t1" }, { id: "e2", source: "n", target: "t2" }] as never;
    const view = panelView({ block: null, blocks: [], cardId: "n", cardName: "Karta", cardPurpose: "Zapisuje metriky.", card: null, trail, edges });
    expect(view.head).toMatchObject({ kind: "card", number: "", id: "n", title: "Karta", text: "Zapisuje metriky.", cardName: "Karta" });
    expect(view.ports.map((p) => [p.label, p.target, p.message])).toEqual([["vazba", "API", "Hotové API"], ["vazba", "Web", ""]]);
  });

  it("jiné karty jménem s pořadím: na co karta čeká a odkud do ní vstup přichází", () => {
    expect([cardLabel("Zápis metrik", 302), cardLabel("Dashboard", null)]).toEqual(["3·02 Zápis metrik", "Dashboard"]);
    const card = { nodeId: "n", stage: "plan", reason: "blocked_by_dependency", blockedBy: ["a"], steps: null, order: null } as never;
    const edges = [{ id: "e1", source: "a", target: "n" }, { id: "e2", source: "a", target: "n" }, { id: "e3", source: "n", target: "b" }] as never;
    const labels: Record<string, string> = { a: "3·02 Zápis metrik", b: "Web" };
    const view = panelView({ block: null, blocks: [], cardId: "n", cardName: "Dashboard", card, trail: null, edges, labelOf: (id) => labels[id] });
    expect(view.work.line).toBe("na kartu 3·02 Zápis metrik");
    expect(view.incoming).toEqual(["3·02 Zápis metrik"]);
  });
});
