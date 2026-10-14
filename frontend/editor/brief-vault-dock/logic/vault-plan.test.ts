import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { buildPlan, defaultSelection, distributeCandidates, planBody, planParent, selectionCandidates, LOGIC_BLOCKS, MAX_PLAN_CARDS } from "./vault-plan";
import { filterByTrack } from "./vault-tracks";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "f" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});

describe("vault plan", () => {
  it("inserts selected fragments as cards with fragmentRef and sub-fragments as blocks", () => {
    const a1 = node("3.12.1 Chunk id"); const a2 = node("3.12.2 Overlap");
    const research = node("research", { kind: "research" });
    const a = node("3.12 Chunks", { mvp: "yes", children: [a1, a2, research], textRevision: 3, revision: 5 });
    const b = node("3.15 Metadata", { mvp: "yes", inserted: true, status: "inserted", cards: [{ nodeId: "c", revision: 1 }] });
    const root = node("3. VRSTVA", { children: [a, b] });
    expect([...defaultSelection([root])]).toEqual([a.id]);
    const plan = buildPlan([root], selectionCandidates([root], new Set([a.id, b.id])), "sector-1");
    expect(plan.cards).toHaveLength(1);
    const [card] = plan.cards;
    expect(card).toMatchObject({ ref: "f1", kind: "node", parent: "@sector-1", name: "[task] 3.12 Chunks", card: { status: "draft" } });
    expect(card.fragmentRef).toEqual([{ fragmentId: a.id }, { fragmentId: a1.id }, { fragmentId: a2.id }]);
    expect(card.blocks.map((block) => [block.ref, block.title])).toEqual([["b1", "3.12.1 Chunk id"], ["b2", "3.12.2 Overlap"]]);
    expect(card.purpose).toBe("Zadání ze schránky: 3. VRSTVA › 3.12 Chunks");
    // Text zadání se nekopíruje, karta říká, kde ho agent najde (a ze které revize textu vznikla).
    expect(card.text).toContain("r3");
    expect(card.text).toContain("node-brief");
    expect(planBody(plan)).toEqual({ nodes: plan.cards });
  });

  it("distributes the rest: untouched branch = one card, partly inserted branch splits into children", () => {
    const done = node("3.1", { inserted: true, status: "inserted", cards: [{ nodeId: "c", revision: 1 }] });
    const rest = node("3.2");
    const mixed = node("3.3 Index", { children: [node("3.3.1 Hotové", { inserted: true, status: "inserted" }), node("3.3.2 Zbývá")] });
    const whole = node("3.4 Cache", { children: [node("3.4.1"), node("3.4.2")] });
    const root = node("Vrstva", { children: [done, rest, mixed, whole] });
    expect(distributeCandidates([root]).map((item) => item.title)).toEqual(["3.2", "3.3.2 Zbývá", "3.4 Cache"]);
    const lone = node("Krátké zadání");
    expect(distributeCandidates([lone]).map((item) => item.title)).toEqual(["Krátké zadání"]);
    expect(distributeCandidates([node("Inserted root", { inserted: true })])).toEqual([]);
  });

  it("caps one batch at 200 cards and reports the rest", () => {
    const many = Array.from({ length: MAX_PLAN_CARDS + 5 }, (_, index) => node("k" + index));
    const root = node("Vrstva", { children: many });
    const plan = buildPlan([root], distributeCandidates([root]), null);
    expect(plan.cards).toHaveLength(MAX_PLAN_CARDS);
    expect(plan.skipped).toBe(5);
    expect(plan.cards[0].parent).toBeNull();
  });

  it("places cards in the sector, next to an owning card, or on the canvas root", () => {
    const nodes = [{ id: "s", kind: "sector", parentId: null }, { id: "c", kind: "node", parentId: "s" }];
    expect(planParent("s", nodes)).toBe("s");
    expect(planParent("c", nodes)).toBe("s");
    expect(planParent("", nodes)).toBeNull();
  });
  it("a card from the CX/UX/UI track lands in the frontend layer with sub-fragment blocks only", () => {
    const screen = node("Obrazovka košíku", { effectiveTrack: "ux", children: [node("Prázdný stav", { effectiveTrack: "ux" })] });
    const [card] = buildPlan([screen], [screen], null).cards;
    expect(card.card).toEqual({ status: "draft", layer: "frontend" });
    expect(card.blocks.map((block) => block.title)).toEqual(["Prázdný stav"]);
  });

  it("a card from the Backend + DB track lands in backend and always ends with the four closing blocks", () => {
    const kids = Array.from({ length: 50 }, (_, index) => node("Pravidlo " + index, { effectiveTrack: "logic" }));
    const rules = node("Výpočet ceny", { track: "logic", effectiveTrack: "logic", children: kids });
    const [card] = buildPlan([rules], [rules], null).cards;
    expect(card.card).toEqual({ status: "draft", layer: "backend" });
    expect(card.blocks).toHaveLength(40);
    expect(card.blocks.slice(0, 36).every((block) => block.title.startsWith("Pravidlo"))).toBe(true);
    expect(card.blocks.slice(36).map((block) => [block.ref, block.title, block.condition])).toEqual([
      ["b37", "Funkce a metody", "Podpisy a odpovědnost každé funkce jsou zapsané."],
      ["b38", "Spolupráce", "Tok dat mezi funkcemi je popsaný."],
      ["b39", "Test částí", "Testy jednotlivých částí prošly."],
      ["b40", "Komponenta", "Komponenta funguje jako celek a test celku prošel."],
    ]);
    expect(card.blocks[39].ports).toEqual([{ ref: "frontend", label: "Komponenta hotová → frontend" }]);
    expect(card.blocks.slice(0, 39).some((block) => block.ports)).toBe(false);
    const lone = node("Invariant", { effectiveTrack: "logic" });
    expect(buildPlan([lone], [lone], null).cards[0].blocks.map((block) => block.title)).toEqual(LOGIC_BLOCKS.map((block) => block.title));
  });

  it("an unassigned card has no layer", () => {
    const old = node("Staré zadání", { effectiveTrack: null });
    expect(buildPlan([old], [old], null).cards[0].card).toEqual({ status: "draft" });
  });

  it("a path-only node of another track never becomes a card", () => {
    const logic = node("Výpočet", { effectiveTrack: "logic", mvp: "yes" });
    const root = node("Zadání", { effectiveTrack: "ux", mvp: "yes", children: [node("Tok", { effectiveTrack: "ux" }), logic] });
    const view = filterByTrack([root], "logic");
    expect(distributeCandidates(view).map((item) => item.title)).toEqual(["Výpočet"]);
    expect([...defaultSelection(view)]).toEqual([logic.id]);
    expect(selectionCandidates(view, new Set([root.id, logic.id])).map((item) => item.title)).toEqual(["Výpočet"]);
  });
});
