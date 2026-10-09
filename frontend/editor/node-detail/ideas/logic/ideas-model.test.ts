import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";
import IdeasPanel, { IdeasCount } from "@/editor/node-detail/ideas/components/IdeasPanel";
import { ideasOf, openIdeas, removeIdea, setIdeaStatus, sortedIdeas, sourceLabel, type CardIdea } from "@/editor/node-detail/ideas/logic/ideas-model";

const idea = (id: string, extra: Partial<CardIdea> = {}): CardIdea => ({
  id, text: `Podnět ${id}`, by: "kritik-sly-2", source: "critic:sly", at: `2026-10-09T10:0${id.length}:00+00:00`, status: "open", ...extra,
});
const withIdeas = (ideas: CardIdea[]): DesktopState => ({
  ...emptyDesktopState(), nodes: { n: { phase: "discover" as const, criteria: [], steps: [], ideas } },
});
const panel = (ideas: CardIdea[], readOnly = false) => renderToStaticMarkup(createElement(IdeasPanel, {
  ideas, readOnly, busy: false, onStatus: () => {}, onRemove: () => {},
}));

describe("podněty k dalšímu vývoji", () => {
  it("počítá jen otevřené a řadí je nahoru", () => {
    const ideas = [idea("a", { status: "done" }), idea("bb"), idea("c")];
    expect(openIdeas(ideas)).toBe(2);
    expect(openIdeas(undefined)).toBe(0);
    expect(sortedIdeas(ideas).map((item) => item.id)).toEqual(["bb", "c", "a"]);
  });

  it("člověk odškrtne, vrátí a smaže podnět; prázdný seznam klíč odebere", () => {
    let state = setIdeaStatus("n", "a", "done")(withIdeas([idea("a"), idea("b")]));
    expect(ideasOf(state, "n").map((item) => item.status)).toEqual(["done", "open"]);
    state = setIdeaStatus("n", "a", "open")(state);
    expect(ideasOf(state, "n")[0].status).toBe("open");
    state = removeIdea("n", "b")(removeIdea("n", "a")(state));
    expect("ideas" in state.nodes.n).toBe(false);
    expect(ideasOf(state, "jiny")).toEqual([]);
  });

  it("seznam ukáže text, původ a mazání jen u odškrtnutého", () => {
    const html = panel([idea("a"), idea("b", { status: "done", source: "review" })]);
    expect(html).toContain("Podnět a");
    expect(html).toContain("kritik: vyčuraný · kritik-sly-2");
    expect(html.match(/Smazat podnět/g)?.length).toBe(1);
    expect(panel([idea("b", { status: "done" })], true)).not.toContain("Smazat podnět");
    expect(panel([])).toContain("Zatím žádné podněty");
    expect(sourceLabel("neznamy")).toBe("neznamy");
  });

  it("odznak počtu se při nule neukáže", () => {
    expect(renderToStaticMarkup(createElement(IdeasCount, { count: 3 }))).toContain(">3<");
    expect(renderToStaticMarkup(createElement(IdeasCount, { count: 0 }))).toBe("");
  });
});
