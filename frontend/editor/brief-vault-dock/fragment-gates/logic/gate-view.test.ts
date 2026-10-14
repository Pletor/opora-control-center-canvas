import { describe, expect, it } from "vitest";
import type { FragmentDetail, GateFlags } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { GATES } from "@/editor/node-detail/brief-vault/logic/gate-bar";
import { deadEndReason, gateRows, payloadLines, queueText, whoLabel } from "./gate-view";

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
      .toEqual(["skutečnost · testy: projdou", "skutečnost · kol kritika: 1", "skutečnost · nečekané: ano"]);
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

  it("describes the agent queue", () => {
    expect(queueText({ fragment: { id: "f", title: "F", effectiveDiscipline: "be", revision: 3 }, gate: "weighed", needs: "confirm", blocked: 2 }, "f"))
      .toBe("Fronta agentů: další na řadě tento fragment · 2. Zváženo (čeká na potvrzení návrhu) · 2 čeká na návrh nebo schválení člověka.");
    expect(queueText({ fragment: null, blocked: 0 }, "f")).toBe("Fronta agentů disciplíny je prázdná.");
    expect(queueText(undefined, "f")).toBe("");
  });
});
