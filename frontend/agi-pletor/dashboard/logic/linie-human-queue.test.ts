import { describe, expect, it } from "vitest";
import { ApiError } from "@/shared/types/logic/types";
import { humanQueueView, humanRequest, idleText, refusalText, verified } from "./linie-human-queue";

const SHA = "9c8050f1a2b3c4d5e6f708192a3b4c5d6e7f8091";
const row = (extra: object = {}) => ({
  ticketId: "tk_c", mark: "OP-C", title: "Vůz C", branch: "feat/a-b-c", target: "feat/a-b", sha: SHA, order: 1, state: "čeká na přijetí 9c8050f",
  next: "Člověk rozhodne.", sentence: "začlení feat/a-b-c do feat/a-b, pak bude na řadě OP-B (feat/a-b)",
  checks: { state: "passed", sha: SHA }, preview: true, action: { kind: "accept_merge", label: "Přijmout a začlenit" }, ...extra,
});

describe("Čeká na tebe", () => {
  it("pořadí bere ze služby beze změny a neznámou akci nenabídne", () => {
    const found = humanQueueView({ queues: { human: [row(), row({ ticketId: "tk_b", order: 2, action: { kind: "smazat" } }), { title: "bez id" }] } });
    expect(found.map((r) => [r.ticketId, r.order])).toEqual([["tk_c", 1], ["tk_b", 2]]);
    expect(found[1].action).toBeNull();
    expect(humanQueueView({ queues: { humanDecisions: 0 } })).toEqual([]);
  });

  it("ověření: kontroly pro revizi a shoda náhledu", () => {
    const [r] = humanQueueView({ queues: { human: [row()] } });
    expect(verified(r)).toBe("kontroly prošly 9c8050f · náhled = revize");
    expect(verified({ ...r, preview: null, checks: { state: "missing", sha: "" } })).toBe("kontroly chybí");
  });

  it("jedno tlačítko = accept-merge s revizí, kterou člověk viděl, a s op", () => {
    const [r] = humanQueueView({ queues: { human: [row()] } });
    expect(humanRequest(r, "op-1")).toEqual({ path: "/work/tk_c/accept-merge", body: { sha: SHA, op: "op-1" }, method: "POST", done: "Začleněno feat/a-b-c do feat/a-b." });
    expect(humanRequest({ ...r, action: { kind: "unblock", label: "Odblokovat" } }, "x")?.path).toBe("/work/tk_c/unblock");
    expect(humanRequest({ ...r, action: null }, "x")).toBeNull();
  });

  it("prázdný stav jmenuje, kdo pracuje", () => {
    const wip = { mark: "OP-W", title: "W", judgement: { summary: { key: "wip" } } } as Parameters<typeof idleText>[0][number];
    expect(idleText([wip], [{ binding: { ticketId: "tk", agent: "agent-a", from: "", to: "", live: true } }])).toBe("Nic nečeká na tebe. Pracují: agent-a, OP-W.");
    expect(idleText([], [])).toBe("Nic nečeká na tebe. Pracují: nikdo.");
  });

  it("409 se vrací větou a jedinou opravou", () => {
    const failure = new ApiError("x", 409, { error: "Začlenění se zastavilo: cíl se posunul.", code: "target_moved", hint: "Klikni znovu." });
    expect(refusalText(failure)).toBe("Začlenění se zastavilo: cíl se posunul. Oprava: Klikni znovu.");
  });
});
