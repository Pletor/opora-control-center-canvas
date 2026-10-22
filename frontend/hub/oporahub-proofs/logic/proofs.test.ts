import { describe, expect, it } from "vitest";
import type { AgentAction } from "@/hub/oporahub-agent-state/logic/agent-state";
import { parseProofs, proofActions, proofRows } from "./card-proofs";
import { ledgerRows, ledgerTiles, parseLedger } from "./proof-ledger";

const head = "a".repeat(40);
const rec = (id: string, tool: string, extra: Record<string, unknown> = {}) => ({ id, nodeId: "task_a", acceptedRevision: head,
  createdAt: `2026-10-2${id.length % 9}T10:00:00Z`, trust: "agent-reported",
  verification: { tool: { name: tool }, source: { commitSha: "c".repeat(40) }, configuration: {} },
  report: { outcome: "passed", createdAt: "2026-10-21T10:00:00Z" }, ...extra });

describe("card proofs", () => {
  it("shows newest lean/tlc record with trust and an empty conformance row", () => {
    const records = parseProofs({ requests: [
      rec("l1", "lean", { trust: "ci-verified", origin: { checkName: "formal-trusted/lean" } }),
      rec("t1", "tlc", { report: { outcome: "counterexample", createdAt: "2026-10-20T10:00:00Z" }, acceptedRevision: "b".repeat(40) }),
      rec("t2", "tlc", { report: { outcome: "passed", createdAt: "2026-10-19T10:00:00Z" } }), { bad: true }] });
    const rows = proofRows(records, head);
    expect(rows.map(row => [row.kind, row.status, row.trust])).toEqual([["lean", "passed", "ci-verified"], ["tlc", "counterexample", "agent-reported"], ["conformance", "not_connected", null]]);
    expect(rows[0]).toMatchObject({ trustLabel: "ověřeno CI", checkName: "formal-trusted/lean", glyph: "✓" });
    expect(rows[1]).toMatchObject({ historical: true, glyph: "✕", trustLabel: "nahlášeno agentem" });
    expect(rows[2].word).toBe("bez záznamu");
  });
  it("classifies a conformance check by its name", () => {
    const rows = proofRows(parseProofs({ requests: [rec("x", "tlc", { origin: { checkName: "formal/conformance" } })] }), head);
    expect(rows.find(row => row.kind === "conformance")?.verificationId).toBe("x");
    expect(rows.find(row => row.kind === "tlc")?.status).toBe("not_connected");
  });
  it("classifies a recorded conformance tool as conformance with its trust", () => {
    const rows = proofRows(parseProofs({ requests: [rec("c", "conformance", { origin: { checkName: "formal/conformance" } })] }), head);
    expect(rows.find(row => row.kind === "conformance")).toMatchObject({ verificationId: "c", status: "passed", trustLabel: "nahlášeno agentem" });
  });
  it("keeps only verification actions targeting this card's records", () => {
    const action = (verb: string, targetId: string): AgentAction => ({ id: `act_${verb}_${targetId}`, verb, method: "POST",
      path: `/api/oporahub/verifications/${targetId}/fix-proposal`, targetId, preconditions: {}, status: "ready" });
    const records = parseProofs({ requests: [rec("t1", "tlc")] });
    expect(proofActions([action("verification.fix", "t1"), action("verification.fix", "other"), action("claim", "t1")], records)
      .map(item => item.verb)).toEqual(["verification.fix"]);
  });
  it("rejects an invalid document", () => { expect(() => parseProofs({})).toThrow(); });
});

describe("proof ledger", () => {
  const ledger = parseLedger({ schemaVersion: 1, allowedAxioms: ["propext"], counts: { proved: 1, unchecked: 1, mystery: 2 },
    entries: [
      { id: "lean:a", tool: "lean", kind: "theorem", name: "a", status: "proved", axioms: ["propext", "sorryAx"], trust: "ci-verified", commitSha: "d".repeat(40) },
      { id: "tlc:b", tool: "tlc", kind: "invariant", name: "b", status: "unchecked", axioms: null, trust: null, commitSha: null }, { nope: 1 }] });
  it("orders tiles by status and keeps unknown statuses", () => {
    expect(ledgerTiles(ledger).map(tile => [tile.status, tile.count])).toEqual([["proved", 1], ["checked", 0], ["counterexample", 0],
      ["failed", 0], ["unverified", 0], ["unchecked", 1], ["mystery", 2]]);
  });
  it("filters by tool and status and flags axioms outside the allowed list", () => {
    expect(ledgerRows(ledger, { tool: "all", status: "all" })).toHaveLength(2);
    const [lean] = ledgerRows(ledger, { tool: "lean", status: "all" });
    expect(lean).toMatchObject({ foreignAxioms: ["sorryAx"], trustLabel: "ověřeno CI", word: "dokázáno", commit: "d".repeat(12) });
    expect(ledgerRows(ledger, { tool: "all", status: "unchecked" }).map(row => row.id)).toEqual(["tlc:b"]);
  });
});
