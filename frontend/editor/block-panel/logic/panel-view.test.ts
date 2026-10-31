import { describe, expect, it } from "vitest";
import { emptyBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { parseCardTrail } from "./card-trail";
import { panelView } from "./panel-view";

describe("panel-view", () => {
  const block = { ...emptyBlock(), number: "1", title: "Zápis metrik", text: "Každá odpověď zapíše metriky." };

  it("hlavička bloku a poslední změna karty (tool.use není změna)", () => {
    const trail = parseCardTrail({ nodeId: "n", judgment: [{ code: "missing_summary" }], recent: [
      { at: "2026-10-31T11:52:00", who: "office", label: "Edit", kind: "tool.use" },
      { at: "2026-10-31T11:51:00", who: "heart", label: "pořadí", kind: "write" }] });
    const view = panelView({ block, blocks: [block], cardName: "Karta", card: null, trail, edges: [], now: new Date("2026-10-31T12:00:00") });
    expect(view.head).toMatchObject({ number: "1", title: "Zápis metrik", cardName: "Karta", order: null,
      change: { who: "Srdce", whoKind: "heart", when: "11:51", what: "pořadí" } });
    expect(view.judgmentViews.map((j) => j.label)).toEqual(["chybí shrnutí"]);
    expect(view.timeline.flatMap((g) => g.items)).toHaveLength(1);
  });

  it("bez stopy prázdná osa, porty i úsudek", () => {
    const empty = panelView({ block, blocks: [block], cardName: "Karta", card: null, trail: null, edges: [] });
    expect([empty.timeline, empty.ports, empty.judgments, empty.head.change, empty.live]).toEqual([[], [], [], null, null]);
  });
});
