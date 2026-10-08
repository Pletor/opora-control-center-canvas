import { describe, expect, it } from "vitest";
import type { SyncReport } from "@/shared/desktop-state/logic/types";
import { assignmentStatusView, githubCommitUrl, syncStatusView } from "./code-status";

const report = (overrides: Partial<SyncReport> = {}): SyncReport => ({
  project: "p", workspace: "w", observedAt: "2026-10-08", gitHead: null, counts: {}, signals: [], verdicts: [], ...overrides,
});

describe("githubCommitUrl", () => {
  it("derives a commit URL only from a GitHub PR repository path and SHA", () => {
    expect(githubCommitUrl("https://github.com/acme/repo/pull/17", "abcdef012345")).toBe("https://github.com/acme/repo/commit/abcdef012345");
    expect(githubCommitUrl("javascript:alert(1)", "abcdef012345")).toBeNull();
    expect(githubCommitUrl("https://example.test/acme/repo/pull/17", "abcdef012345")).toBeNull();
    expect(githubCommitUrl("https://github.com/acme/repo/issues/17", "abcdef012345")).toBeNull();
    expect(githubCommitUrl("https://github.com/acme/repo/pull/17", "not a sha")).toBeNull();
  });
});

describe("assignmentStatusView", () => {
  it("does not treat an absent assignment status as unchanged", () => {
    expect(assignmentStatusView(undefined).kind).toBe("unavailable");
    expect(assignmentStatusView("current").kind).toBe("current");
    expect(assignmentStatusView("changed").kind).toBe("changed");
    expect(assignmentStatusView("unbound").kind).toBe("unbound");
  });
});

describe("syncStatusView", () => {
  it("requires a matching green node verdict before calling empty signals synchronized", () => {
    expect(syncStatusView(report(), "n1").kind).toBe("missing");
    expect(syncStatusView(report({ verdicts: [{ scope: { kind: "node", id: "n1" }, state: "green", canCommit: true, canMerge: true, checks: [], blocking: [], nextSteps: [] }] }), "n1").kind).toBe("synced");
  });

  it("classifies only documented matching evidence and exposes unsupported or mixed evidence", () => {
    const appAhead = report({ signals: [{ id: "s", type: "spec-ahead", severity: "high", subject: { scope: "node", id: "n1", path: null, specRevision: 2 }, evidence: { expected: "revize 2", actual: "pár chybí", source: "pár" }, action: "zadej práci" }] });
    expect(syncStatusView(appAhead, "n1").kind).toBe("app-ahead");
    expect(syncStatusView(report({ signals: [{ ...appAhead.signals[0], type: "source-missing" }] }), "n1").kind).toBe("unsupported");
    expect(syncStatusView(report({ verdicts: [{ scope: { kind: "node", id: "n1" }, state: "green", canCommit: true, canMerge: true, checks: [], blocking: [], nextSteps: [] }], signals: appAhead.signals }), "n1").kind).toBe("mixed");
  });
});
