import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { coverageOf } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { ideaTarget } from "../../logic/disciplines";
import { distributeCandidates } from "../../logic/vault-candidates";
import { flatten } from "../../logic/vault-dock-model";
import { duelItemOf, openDuelCount, splitVault } from "./duel-tree";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> & { kind?: string } = {}): VaultNode => ({
  id: "n" + ++seq, revision: 1, parentId: null, scopeNodeId: "s", ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
} as VaultNode);

describe("duel tree", () => {
  it("removes duel and vision fragments from the tree other sections see", () => {
    const duel = node("Duel o tok", { kind: "duel" } as never);
    const leaf = node("Kapitola");
    const brief = node("Zadání", { children: [leaf, duel] });
    const vision = node("Představa", { kind: "vision" } as never);
    const split = splitVault([vision, brief]);
    expect(split.roots.map((root) => root.title)).toEqual(["Zadání"]);
    expect(flatten(split.roots).map((item) => item.node.title)).toEqual(["Zadání", "Kapitola"]);
    expect(split.duels.map((item) => item.title)).toEqual(["Duel o tok"]);
    expect(split.visions.map((item) => item.title)).toEqual(["Představa"]);
    // Kořen představy by se jinak stal cílem Podnětu; teď cíl zůstane kořen zadání.
    expect(ideaTarget(split.roots, "s", "none", null)).toEqual({ parentId: brief.id });
    expect(coverageOf(split.roots).leaves).toBe(1);
    expect(distributeCandidates(split.roots).map((item) => item.title)).toEqual(["Kapitola"]);
  });

  it("keeps the same objects when there is nothing to remove", () => {
    const roots = [node("A", { children: [node("B")] })];
    expect(splitVault(roots).roots[0]).toBe(roots[0]);
  });

  it("list item comes from the tree summary, counts open duels", () => {
    const duel = node("Duel", { kind: "duel" } as never);
    expect(duelItemOf(duel)).toEqual({ id: duel.id, title: "Duel", status: "open", p: null, open: true });
    const decided = duelItemOf({ ...duel, duel: { status: "decided", subject: { kind: "project", id: "p" }, turns: 4, scores: 2, p: 0.3, outcome: "keep" } } as never);
    expect(decided).toMatchObject({ status: "decided", p: 0.3, open: false });
    expect(duelItemOf({ ...duel, duel: { status: "grill", p: 0.6 } } as never)).toMatchObject({ status: "grill", p: 0.6 });
    expect(openDuelCount([duelItemOf(duel), decided])).toBe(1);
  });
});
