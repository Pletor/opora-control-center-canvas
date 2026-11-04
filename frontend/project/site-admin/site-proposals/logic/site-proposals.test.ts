import { describe, expect, it } from "vitest";
import { diffLines, pendingProposal, valueText } from "./site-proposals";

const proposal = { id: "sp_1", status: "pending", baseRevision: 3, diffTotal: 2, notes: [], note: "", by: "heart", at: "2026-11-04T10:00:00+00:00",
  diff: [{ path: "title", before: "Ember", after: "Ember 2" }, { path: "design.tokens.color.tokens[4].value", before: null, after: { light: "#111" } }] };

describe("návrhy srdce ve Správě webu", () => {
  it("čte jen první čekající návrh a cizí tvar zahodí", () => {
    expect(pendingProposal({ proposals: [proposal] })?.id).toBe("sp_1");
    expect(pendingProposal({ proposals: [] })).toBeNull();
    expect(pendingProposal({ proposals: [{ id: 3 }] })).toBeNull();
    expect(pendingProposal(null)).toBeNull();
  });
  it("rozdíl je řádek na list: cesta, předtím a potom", () => {
    expect(diffLines(proposal)).toEqual([{ path: "title", before: "„Ember“", after: "„Ember 2“" },
      { path: "design.tokens.color.tokens[4].value", before: "—", after: '{"light":"#111"}' }]);
    expect(diffLines(proposal, 1)).toHaveLength(1);
    expect(valueText("x".repeat(100), 10)).toBe("„xxxxxxxx…");
  });
});
