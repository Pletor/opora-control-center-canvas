import { describe, expect, it } from "vitest";
import type { AgentCardStage } from "@/hub/oporahub-agent-state/logic/agent-state";
import { guardLabel, guardsByNode, guardsKey, sumGuards } from "./guard-tally";

const card = (nodeId: string, guardFindings?: AgentCardStage["guardFindings"]): AgentCardStage =>
  ({ nodeId, stage: "work", health: "ok", reason: "", executionId: null, guardFindings });

describe("guard tally", () => {
  it("keeps only cards with open findings", () => {
    const guards = guardsByNode([card("a", { count: 2, severity: "warn" }), card("b"), card("c", { count: 0, severity: "block" })]);
    expect([...guards]).toEqual([["a", { count: 2, severity: "warn" }]]);
    expect(guardsByNode(undefined).size).toBe(0);
    expect(new Map(JSON.parse(guardsKey(guards)))).toEqual(guards);
    expect(guardsKey(new Map())).toBe("");
  });

  it("sums counts and keeps the worst severity", () => {
    expect(sumGuards([{ count: 1, severity: "info" }, undefined, { count: 3, severity: "block" }, { count: 2, severity: "warn" }]))
      .toEqual({ count: 6, severity: "block" });
    expect(sumGuards([{ count: 1, severity: "warn" }, { count: 1, severity: "info" }])).toEqual({ count: 2, severity: "warn" });
    expect(sumGuards([null, { count: 0, severity: "block" }])).toBeNull();
  });

  it("says the count and severity in Czech", () => {
    expect(guardLabel({ count: 1, severity: "info" })).toBe("Strážci: 1 nález (informace)");
    expect(guardLabel({ count: 2, severity: "block" })).toBe("Strážci: 2 nálezy (blokuje)");
    expect(guardLabel({ count: 5, severity: "warn" })).toBe("Strážci: 5 nálezů (varování)");
  });
});
