import { describe, expect, it, vi } from "vitest";
import { parseProcess, processEndpoint, processPresentation, proposeProcessImprovement, PROCESS_STATES } from "./process-sync";
import { processFixture } from "./process-fixtures";

describe("process wire and presentation", () => {
  it("accepts the exact scoped snapshot and scopes a copyable read endpoint", () => {
    const value = processFixture("other", "workspace-2");
    expect(parseProcess(value, "other", "workspace-2")).toEqual(value);
    expect(processEndpoint("other", "workspace-2")).toBe("/api/oporahub/process?project=other&workspace=workspace-2");
  });
  it("rejects wrong scope/schema, unbounded/duplicate cards, malformed tracking and missing availability", () => {
    const value = processFixture();
    for (const bad of [{ ...value, schema: "other" }, { ...value, project: "other" }, { ...value, workspace: "other" },
      { ...value, observedAt: "invalid" }, { ...value, items: [value.items[0], value.items[0]] },
      { ...value, items: Array(101).fill(value.items[0]) }, { ...value, githubTracking: { ...value.githubTracking, scope: "card" } },
      { ...value, items: [{ ...value.items[0], status: "verified-and-deployed" }] },
      { ...value, items: [{ ...value.items[0], executionAvailability: null }] }]) {
      expect(() => parseProcess(bad, "draft", "draft")).toThrow();
    }
  });
  it("keeps reported, historical and ready distinct without inventing authority or proposal identity", () => {
    const card = processFixture().items[0];
    const labels = PROCESS_STATES.map(status => processPresentation({ ...card, status }).label);
    expect(new Set(labels).size).toBe(PROCESS_STATES.length);
    expect(processPresentation({ ...card, status: "reported" }).label).toContain("vyžaduje kontrolu");
    expect(processPresentation({ ...card, status: "stale" }).label).toContain("Historický");
    expect(processPresentation({ ...card, status: "needs-acceptance" }).target).toMatchObject({ kind: "changes" });
    expect(processPresentation({ ...card, status: "needs-acceptance" }).target.id).toBeUndefined();
    const execution = { id: "b".repeat(32), state: "reported", acceptedRevision: "c".repeat(40), matchesCurrentRevision: false, results: 1 };
    expect(processPresentation({ ...card, status: "stale", currentExecution: execution }).target.id).toBe(execution.id);
    expect(processPresentation({ ...card, status: "ready" }).target.id).toBeUndefined();
  });
  it("feedback selects the exact card then opens the native editor without a proposal ID or a write", () => {
    const selected = vi.fn(), open = vi.fn();
    proposeProcessImprovement("card-specific", "Konkrétní karta", selected, open);
    expect(selected).toHaveBeenCalledExactlyOnceWith("card-specific");
    expect(open).toHaveBeenCalledExactlyOnceWith({ kind: "changes", title: "Navrhnout zlepšení · Konkrétní karta · card-specific" });
    expect(selected.mock.invocationCallOrder[0]).toBeLessThan(open.mock.invocationCallOrder[0]);
  });
});
