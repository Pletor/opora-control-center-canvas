import { describe, expect, it } from "vitest";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";
import { ideasOf, openIdeas, removeIdea, setIdeaStatus, sortedIdeas, sourceLabel, type CardIdea } from "@/editor/node-detail/ideas/logic/ideas-model";

const idea = (id: string, extra: Partial<CardIdea> = {}): CardIdea => ({
  id, text: `Podnět ${id}`, by: "kritik-sly-2", source: "critic:sly", at: `2026-10-09T10:0${id.length}:00+00:00`, status: "open", ...extra,
});
const withIdeas = (ideas: CardIdea[]): DesktopState => ({
  ...emptyDesktopState(), nodes: { n: { phase: "discover" as const, criteria: [], steps: [], ideas } },
});

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

  it("neznámý původ podnětu se ukáže doslova", () => {
    expect(sourceLabel("neznamy")).toBe("neznamy");
  });
});
