import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { defaultSelection, distributeCandidates, planRequest, selectionCandidates } from "./vault-candidates";
import { filterByTrack } from "./vault-tracks";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "f" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});

describe("vault candidates", () => {
  it("selects confirmed MVP chapters without a card, in tree order", () => {
    const a = node("3.12 Chunks", { mvp: "yes", children: [node("3.12.1"), node("research", { kind: "research" })] });
    const b = node("3.15 Metadata", { mvp: "yes", inserted: true, status: "inserted", cards: [{ nodeId: "c", revision: 1 }] });
    const root = node("3. VRSTVA", { children: [a, b] });
    expect([...defaultSelection([root])]).toEqual([a.id]);
    expect(selectionCandidates([root], new Set([b.id, a.id])).map((item) => item.title)).toEqual(["3.12 Chunks"]);
    expect(planRequest(selectionCandidates([root], new Set([a.id])))).toEqual({ fragmentIds: [a.id] });
  });

  it("distributes the rest: untouched branch = one candidate, partly inserted branch splits into children", () => {
    const done = node("3.1", { inserted: true, status: "inserted", cards: [{ nodeId: "c", revision: 1 }] });
    const rest = node("3.2");
    const mixed = node("3.3 Index", { children: [node("3.3.1 Hotové", { inserted: true, status: "inserted" }), node("3.3.2 Zbývá")] });
    const whole = node("3.4 Cache", { children: [node("3.4.1"), node("3.4.2")] });
    const root = node("Vrstva", { children: [done, rest, mixed, whole] });
    expect(distributeCandidates([root]).map((item) => item.title)).toEqual(["3.2", "3.3.2 Zbývá", "3.4 Cache"]);
    expect(distributeCandidates([node("Krátké zadání")]).map((item) => item.title)).toEqual(["Krátké zadání"]);
    expect(distributeCandidates([node("Inserted root", { inserted: true })])).toEqual([]);
  });

  it("a path-only node of another track never becomes a candidate", () => {
    const logic = node("Výpočet", { effectiveTrack: "logic", mvp: "yes" });
    const root = node("Zadání", { effectiveTrack: "ux", mvp: "yes", children: [node("Tok", { effectiveTrack: "ux" }), logic] });
    const view = filterByTrack([root], "logic");
    expect(distributeCandidates(view).map((item) => item.title)).toEqual(["Výpočet"]);
    expect([...defaultSelection(view)]).toEqual([logic.id]);
    expect(selectionCandidates(view, new Set([root.id, logic.id])).map((item) => item.title)).toEqual(["Výpočet"]);
  });

  it("one plan request carries at most 500 fragments (server limit)", () => {
    const many = Array.from({ length: 505 }, (_, index) => node("k" + index));
    expect(planRequest(many).fragmentIds).toHaveLength(500);
  });
});
