import { describe, expect, it } from "vitest";
import type { ReviewGate } from "@/hub/oporahub-review-gate/logic/review-gate";
import { cardFindings, freshness, gateRules, parseFindings, severityCounts } from "./review-view";

const gate = (reasons: string[], extra: Partial<ReviewGate["mergeReadiness"]> = {}): ReviewGate => ({
  executionId: "ex1", cardId: "c1", repository: "o/r", number: 145, headSha: "abc", prState: "open", reviewJobId: "j1", round: 1, riskTier: "standard",
  mergeReadiness: { template: { missing: [] }, base: { baseRef: "main", baseSha: "b", mergeBaseSha: null, behindBy: 2, fresh: false }, ...extra },
  reviewGate: { status: reasons.length ? "blocked" : "ready", openImportant: 1, requiredHumanApprovals: 1, humanApprovalsAtHead: 0, reasons } });
const raw = (id: string, number: number, severity: string, status: string, round = 1) =>
  ({ findingId: id, repository: "o/r", number, severity, status, round, title: id, path: "src/a.ts", line: 3 });

describe("review tab", () => {
  it("parses findings and keeps only those of the card PR, open and severe first", () => {
    const all = parseFindings({ findings: [raw("minor", 145, "minor", "open"), raw("fixed", 145, "important", "fixed"),
      raw("crit", 145, "important", "open"), raw("other", 9, "important", "open"), { bad: 1 }] });
    expect(all).toHaveLength(4);
    const mine = cardFindings(all, gate([]));
    expect(mine.map(item => item.findingId)).toEqual(["crit", "minor", "fixed"]);
    expect(severityCounts(mine)).toEqual({ open: 2, important: 1, total: 3 });
    expect(cardFindings(all, null)).toEqual([]);
    expect(parseFindings({ enabled: false })).toEqual([]);
  });
  it("lists every gate reason and the rules that already hold", () => {
    const rows = gateRules(gate(["open_important_findings", "stale_against_main", "human_approvals_missing"]));
    expect(rows.slice(0, 3).map(row => [row.code, row.state])).toEqual([
      ["open_important_findings", "blocked"], ["stale_against_main", "pending"], ["human_approvals_missing", "pending"]]);
    expect(rows.find(row => row.code === "template")?.state).toBe("ok");
    expect(rows.some(row => row.code === "stale")).toBe(false);
    expect(rows.at(-1)).toMatchObject({ code: "security", state: "off" });
  });
  it("describes freshness against the target branch", () => {
    expect(freshness(gate([]))).toEqual({ text: "2 commitů za main", tone: "warn" });
    expect(freshness(gate([], { base: null })).tone).toBe("gap");
  });
});
