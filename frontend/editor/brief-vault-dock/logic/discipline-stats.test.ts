import { describe, expect, it } from "vitest";
import type { GateFlags, VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { disciplineStats } from "./discipline-stats";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "s" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});
const verified = (error: number) => ({ predictionError: error } as GateFlags);

describe("discipline stats", () => {
  it("covers each discipline and averages its prediction error", () => {
    const root = node("Zadání", { effectiveDiscipline: "ux", children: [
      node("Tok", { effectiveDiscipline: "ux", status: "inserted", inserted: true, gates: verified(0.4) }),
      node("Obrazovka", { effectiveDiscipline: "ux", gates: verified(0) }),
      node("Výpočet", { effectiveDiscipline: "be", children: [node("Sleva", { effectiveDiscipline: "be" }), node("Daň", { effectiveDiscipline: "be", status: "changed" })] }),
    ] });
    const old = node("Staré", { children: [node("1")] });
    const stats = disciplineStats([root, old]);
    expect(stats.map((item) => item.id)).toEqual(["ux", "be", "none"]);
    expect(stats[0]).toMatchObject({ asCards: 1, meanError: 0.2, verified: 2 });
    expect(stats[0].coverage.leaves).toBe(2);
    expect(stats[1]).toMatchObject({ asCards: 1, meanError: null, verified: 0 });
    expect(stats[1].coverage.leaves).toBe(2);
    expect(stats[2].coverage.leaves).toBe(1);
  });
});
