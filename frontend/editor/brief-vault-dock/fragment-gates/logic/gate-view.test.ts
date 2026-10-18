import { describe, expect, it } from "vitest";
import type { FragmentDetail, GateFlags } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { GATES } from "@/editor/node-detail/brief-vault/logic/gate-bar";
import type { GateProposal } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { blockReason, deadEndReason, gateRows, roundLine, payloadLines, proposalStatus, queueText, verifiedOutcome, whoLabel } from "./gate-view";

const flags = (count: number): GateFlags => ({
  ...Object.fromEntries(GATES.map((gate, index) => [gate, index < count])) as Record<(typeof GATES)[number], boolean>, predictionError: null,
});
const detail = (extra: Partial<FragmentDetail> = {}): FragmentDetail => ({
  fragment: { id: "f", revision: 3, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title: "F", stage: "draft", mvp: "none",
    note: "", by: "", actor: "", at: "", deleted: false, chars: 1, text: "t" },
  latestRevision: 3, history: [], path: [], scopeNodeId: null, status: "saved", children: [], cards: [], ideas: [],
  effectiveDiscipline: "be", gates: flags(2), gateStep: 2, gatesStale: false, deadEnd: false, gateDetail: {}, ...extra,
});

describe("gate view", () => {
  it("reads payloads in Czech and skips the stored plan and the prediction error", () => {
    expect(payloadLines({ verdict: "no", reason: "Duplicitní." })).toEqual(["rozhodnutí: ne", "důvod: Duplicitní."]);
    expect(payloadLines({ actual: { tests: "pass", criticRounds: 1, unexpected: true }, predictionError: 0.33 }))
      .toEqual(["skutečnost · kol kritika: 1", "skutečnost · nečekané: ano"]);
    expect(payloadLines({ plan: { nodes: [] }, hash: "abc" })).toEqual(["otisk plánu: abc"]);
    expect(payloadLines(null)).toEqual([]);
  });

  it("names who wrote a gate", () => {
    expect(whoLabel("Hermes", "agent")).toBe("agent Hermes");
    expect(whoLabel("", "human")).toBe("člověk");
  });

  it("marks the next gate and why it waits; a dead end has no next gate", () => {
    const rows = gateRows(detail());
    expect(rows.map((row) => [row.on, row.next])).toEqual([[true, false], [true, false], [false, true], [false, false],
      [false, false], [false, false], [false, false], [false, false]]);
    expect(gateRows(detail({ effectiveDiscipline: null }))[2].waiting).toContain("nemá disciplínu");
    const dead = detail({ gates: flags(4), gateStep: 4, deadEnd: true,
      gateDetail: { decided: { value: true, payload: { verdict: "no", reason: "Mimo rozsah." }, by: "", actor: "", at: "", inputHash: "", revision: 2, valid: true } } });
    expect(gateRows(dead).some((row) => row.next)).toBe(false);
    expect(deadEndReason(dead)).toBe("Mimo rozsah.");
  });

  it("an entry switched on under other inputs is stale", () => {
    const stale = detail({ gates: flags(0), gateStep: 0, gatesStale: true,
      gateDetail: { scoped: { value: true, payload: null, by: "", actor: "", at: "", inputHash: "x", revision: 1, valid: false } } });
    expect(gateRows(stale)[0]).toMatchObject({ on: false, stale: true, next: true });
  });

  it("tells who proposed a gate and what happened to the proposal", () => {
    const proposal: GateProposal = { id: "p", revision: 2, gate: "weighed", payload: {}, note: "", by: "Hermes", actor: "agent",
      at: "", status: "pending", rejection: null };
    expect(proposalStatus(proposal)).toBe("navrhl agent Hermes · čeká na potvrzení");
    expect(proposalStatus({ ...proposal, status: "used" })).toBe("navrhl agent Hermes · použit");
    expect(proposalStatus({ ...proposal, status: "rejected",
      rejection: { id: "r", note: "Riziko chybí.", by: "Claude", actor: "agent", at: "" } }))
      .toBe("navrhl agent Hermes · zamítl agent Claude: Riziko chybí.");
    expect(proposalStatus({ ...proposal, status: "rejected",
      rejection: { id: null, note: "", by: "", actor: "human", at: "", gateOff: true } }))
      .toBe("navrhl agent Hermes · neplatí (brána vypnuta po návrhu)");
  });

  it("describes the agent queue", () => {
    expect(queueText({ fragment: { id: "f", title: "F", effectiveDiscipline: "be", revision: 3 }, gate: "weighed", needs: "confirm", blocked: 2 }, "f"))
      .toBe("Fronta agentů: další na řadě tento fragment · 2. Zváženo (čeká na potvrzení návrhu) · 2 čeká na návrh nebo schválení člověka.");
    expect(queueText({ fragment: null, blocked: 0 }, "f")).toBe("Fronta agentů disciplíny je prázdná.");
    expect(queueText(undefined, "f")).toBe("");
  });

  it("shows the round and why a fragment waits", () => {
    expect(roundLine(detail({ round: 2, exhausted: false }))).toEqual({ text: "kolo 2/3 · čeká na návrh", exhausted: false });
    expect(roundLine(detail({ round: 4, exhausted: true }))).toEqual({ text: "vyčerpáno – čeká na člověka", exhausted: true });
    expect(roundLine(detail())).toBeNull();
    expect(blockReason(detail({ gateStep: 5, gates: flags(5) }))).toBe("čeká na schválení vložení");
  });

  it("keeps steps and layer out of the payload lines and breaks down the queue block", () => {
    expect(payloadLines({ type: "code", steps: ["A"], layer: "backend" })).toEqual(["typ: code"]);
    expect(queueText({ fragment: null, blocked: 3, blockedBy: { proposal: 2, exhausted: 1 } }, "f"))
      .toBe("Fronta agentů disciplíny je prázdná · 3 čeká (2× na návrh, 1× vyčerpáno, na člověka).");
    expect(queueText({ fragment: { id: "d", title: "Duel: X", effectiveDiscipline: "be", revision: 2 }, gate: null, needs: "duel",
      hint: "Duel: na tahu A", blocked: 2, blockedBy: { duel: 2 } }, "f"))
      .toBe("Na řadě duel: na tahu A · 2 čeká (čeká na duel 2).");
  });

  it("verified outcome keeps plan approval and tests apart", () => {
    expect(verifiedOutcome({ tests: "fail", planApproved: true, planScore: 8 }))
      .toEqual({ plan: { approved: true, text: "plán schválen 8/10" }, tests: { state: "fail", text: "testy neprošly" } });
    expect(verifiedOutcome({ tests: "pass", planApproved: false, planScore: 6 })?.plan.text).toBe("plán neschválen 6/10");
    expect(verifiedOutcome({ tests: "untested", planApproved: true })).toMatchObject({ plan: { text: "plán schválen" }, tests: { state: "untested", text: "testy neběžely" } });
  });

  it("an old payload without planApproved derives it from the tests", () => {
    expect(verifiedOutcome({ tests: "pass" })?.plan).toEqual({ approved: true, text: "plán schválen" });
    expect(verifiedOutcome({ tests: "fail" })?.plan).toEqual({ approved: false, text: "plán neschválen" });
    expect(verifiedOutcome({ tests: "untested" })?.plan.approved).toBe(false);
    expect(verifiedOutcome(undefined)).toBeNull();
  });
});
