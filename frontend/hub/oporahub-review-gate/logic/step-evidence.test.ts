import { describe, expect, it } from "vitest";
import { parseGates } from "./review-gate";
import { gateView } from "./gate-view";
import { parseStepEvidence, stepEvidenceView } from "./step-evidence";

const steps = {
  decisions: 1,
  items: [
    { id: "s1", title: "Model", status: "done", reported: "done", executionId: "e1", source: "checkpoint", at: "t",
      evidence: { checks: ["pytest"], commits: ["abc1234def"], notes: "ok" }, evidenced: true },
    { id: "s2", title: "API", status: "blocked", reported: "failed", executionId: "e1", source: "result", at: "t",
      evidence: { checks: [], commits: [], notes: "CI red" }, evidenced: true },
    { id: "s3", title: "", status: "missing", reported: null, executionId: null, source: null, at: null,
      evidence: { checks: [], commits: [], notes: "" }, evidenced: false },
    { id: 7, status: "done" },
  ],
  verdict: { status: "incomplete", total: 3, done: 1, blocked: ["s2"], missing: ["s3"], withoutEvidence: ["s3"] },
};
const gate = (evidence?: unknown) => ({ executionId: "e1", cardId: "a", repository: "o/r", number: 7, headSha: "h", prState: "open",
  mergeReadiness: {}, reviewGate: { status: "pending", openImportant: 0, requiredHumanApprovals: 1, humanApprovalsAtHead: 0, reasons: [] },
  ...(evidence === undefined ? {} : { evidence }) });

describe("merge gate evidence per plan step", () => {
  it("parses evidence.steps, drops invalid items and tolerates gates without steps", () => {
    const parsed = parseStepEvidence(steps);
    expect(parsed?.items.map(item => item.id)).toEqual(["s1", "s2", "s3"]);
    expect(parseStepEvidence(null)).toBeNull();
    const [withSteps, without] = parseGates({ items: [gate({ steps }), gate()] });
    expect(withSteps.stepEvidence?.verdict.missing).toEqual(["s3"]);
    expect(without.stepEvidence).toBeNull();
    expect(gateView(without, []).steps).toBeNull();
  });
  it("flags steps that are not done or carry no evidence", () => {
    const view = stepEvidenceView(parseStepEvidence(steps)!);
    expect(view.ok).toBe(false);
    expect(view.headline).toBe("1/3 kroků hotovo · 1 rozhodnutí");
    expect(view.flags).toEqual(["zablokováno: s2", "nenahlášeno: s3", "bez dokladu: s3"]);
    expect(view.rows.map(row => [row.glyph, row.title, row.flagged, row.detail])).toEqual([
      ["✓", "Model", false, "kontroly: pytest · commity: abc1234 · ok"],
      ["✕", "API", true, "CI red"],
      ["–", "s3", true, "krok nikdo nenahlásil"],
    ]);
    const all = stepEvidenceView(parseStepEvidence({ ...steps, decisions: 0, items: steps.items.slice(0, 1),
      verdict: { status: "evidenced", total: 1, done: 1, blocked: [], missing: [], withoutEvidence: [] } })!);
    expect([all.ok, all.headline, all.flags]).toEqual([true, "1/1 kroků hotovo a doloženo", []]);
  });
});
