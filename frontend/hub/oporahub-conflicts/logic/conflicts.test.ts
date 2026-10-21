import { describe, expect, it } from "vitest";
import { conflictsUrl, fieldRows, parseConflicts, resolutionDraft, resolveError, resolveUrl, showValue, validProposalId } from "./conflicts";

const raw = { acceptedHead: "h".repeat(40), enabled: true, items: [{ id: "c1", status: "open", resolutionProposalId: null,
  createdAt: "2026-10-20", updatedAt: "2026-10-20", proposalKind: "changeset", proposalId: "cs9", acceptedHead: "h".repeat(40),
  items: [{ key: "goal", base: "A", ours: "B", theirs: "C" }, { key: "acceptance", base: ["x"], ours: ["x", "y"], theirs: ["x", "z"] }] }] };

describe("auto-rebase conflicts", () => {
  it("parses the list and rejects an unknown status", () => {
    const list = parseConflicts(raw);
    expect(list.items[0].items).toHaveLength(2);
    expect(list.enabled).toBe(true);
    expect(parseConflicts({ ...raw, enabled: false }).enabled).toBe(false);
    expect(() => parseConflicts({ items: [{ ...raw.items[0], status: "weird" }] })).toThrow();
  });
  it("builds urls with an optional status filter", () => {
    expect(conflictsUrl("p", "w", "open")).toBe("/api/oporahub/auto-rebase/conflicts?project=p&workspace=w&status=open");
    expect(conflictsUrl("p", "w", "all")).not.toContain("status");
    expect(resolveUrl("a/b")).toBe("/api/oporahub/auto-rebase/conflicts/a%2Fb/resolve");
  });
  it("marks which side differs from base and carries the choice", () => {
    const rows = fieldRows(parseConflicts(raw).items[0], { goal: "theirs" });
    expect(rows[0]).toMatchObject({ key: "goal", oursChanged: true, theirsChanged: true, choice: "theirs" });
    expect(rows[1]).toMatchObject({ ours: "[\"x\",\"y\"]", choice: "" });
    expect(showValue(null)).toBe("—");
  });
  it("drafts a resolution and reports when undecided fields remain", () => {
    const item = parseConflicts(raw).items[0];
    const partial = resolutionDraft(item, { goal: "ours" });
    expect(partial.complete).toBe(false);
    expect(partial.text).toContain("goal: B (z návrhu)");
    expect(partial.text).toContain("acceptance: NEROZHODNUTO");
    expect(resolutionDraft(item, { goal: "ours", acceptance: "theirs" }).complete).toBe(true);
  });
  it("translates a rejected resolution to Czech and validates the id", () => {
    expect(resolveError(409, "x")).toBe("Řešení musí být jiný návrh nad aktuální hlavou.");
    expect(resolveError(500, "boom")).toBe("boom");
    expect(validProposalId(" cs_10 ")).toBe(true);
    expect(validProposalId("a b")).toBe(false);
  });
});
