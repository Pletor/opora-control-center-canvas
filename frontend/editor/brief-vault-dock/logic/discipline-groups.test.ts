import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { DISCIPLINES, UNASSIGNED } from "./disciplines";
import { activeGroup, groupTarget, groupWaiting, nextWaiting, totalWaiting, waitingByDiscipline } from "./discipline-groups";

const live = DISCIPLINES.filter((item) => ["ux", "be", "api", "devops"].includes(item.id));

function node(id: string, extra: Partial<VaultNode> = {}): VaultNode {
  return {
    id, title: id, text: "", kind: "brief", parentId: null, ord: 0, revision: 1, stage: "draft", mvp: "none",
    scopeNodeId: null, status: "saved", children: [], cards: [], discipline: null, effectiveDiscipline: null, offPath: false,
    ...extra,
  } as VaultNode;
}

describe("skupiny přepínače disciplín", () => {
  it("otevřená skupina je skupina vybrané disciplíny, Nezařazené žádnou", () => {
    expect(activeGroup("be", live)).toBe("logika");
    expect(activeGroup("ux", live)).toBe("kresleni");
    expect(activeGroup(UNASSIGNED, live)).toBeNull();
  });

  it("hlavička vede nejdřív tam, kde něco čeká, pak k obsahu, pak k první zapnuté; spící skupina nikam", () => {
    const counts = { ux: 2, be: 0, api: 3, devops: 1 };
    expect(groupTarget("logika", live, counts, { api: 1 })).toBe("api");
    expect(groupTarget("logika", live, counts, {})).toBe("api");
    expect(groupTarget("logika", live, { ux: 2, be: 0, api: 0, devops: 1 }, {})).toBe("be");
    expect(groupTarget("kresleni", DISCIPLINES.filter((item) => item.id === "be"), counts, {})).toBeNull();
  });

  it("„Čeká na tebe“ jde dokola na další disciplínu s čekající věcí, Nezařazené na konci", () => {
    const waiting = { ux: 1, api: 0, devops: 2, [UNASSIGNED]: 1 };
    expect(nextWaiting("ux", live, waiting)).toBe("devops");
    expect(nextWaiting("devops", live, waiting)).toBe(UNASSIGNED);
    expect(nextWaiting(UNASSIGNED, live, waiting)).toBe("ux");
    expect(nextWaiting("be", live, {})).toBeNull();
    expect(groupWaiting("provoz", live, waiting)).toBe(2);
    expect(totalWaiting(waiting)).toBe(4);
  });

  it("počítá čekající věci na disciplínu ze stromu zúženého jako pohled", () => {
    const roots = [
      node("r1", { discipline: "be", effectiveDiscipline: "be", children: [
        node("q1", { kind: "question", parentId: "r1", effectiveDiscipline: "be", question: { askedFor: "human", answered: false } } as Partial<VaultNode>),
      ] }),
      node("r2", { discipline: "ux", effectiveDiscipline: "ux", mvp: "proposed" }),
      node("r3"),
    ];
    const waiting = waitingByDiscipline(roots, live, []);
    expect(waiting.be).toBe(1);
    expect(waiting.ux).toBe(1);
    expect(waiting.api).toBe(0);
    expect(waiting[UNASSIGNED]).toBe(0);
  });
});
