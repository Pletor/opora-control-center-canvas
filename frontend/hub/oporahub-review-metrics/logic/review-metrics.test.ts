import { describe, expect, it } from "vitest";
import { duration, evalExportUrl, metricsView, parseEvalCount, parseReviewMetrics, percent } from "./review-metrics";

export const metricsFixture = (over: Record<string, unknown> = {}) => ({
  projectId: "p", workspaceId: "w", window: "30d", since: 0, now: 1, prsReviewed: 4,
  findingsBySeverity: { important: 3, nit: 6, pre_existing: 1 },
  findingOutcomes: { fixed: 3, resolvedWithoutFix: 1, rejectedByVoters: 2, open: 4 },
  findingAcceptanceRate: 0.75, voterRejectionRate: 0.1667, roundsPerPr: { mean: 1.5, max: 3 }, securityRounds: { mean: 0.25, max: 1 },
  humanApprovalsPerPr: 1, timeToHumanDecisionSeconds: { samples: 2, median: 5400, mean: 7200 },
  guardrails: { revertRate: 0.25, incidentRate: 0 }, incidents: [], prs: [], truncated: false, ...over,
});

describe("review metrics", () => {
  it("builds bars scaled to the largest value and rate tiles", () => {
    const view = metricsView(parseReviewMetrics(metricsFixture()));
    expect(view.severity.map(bar => [bar.metric, bar.pct])).toEqual([["findingsBySeverity.important", 50], ["findingsBySeverity.nit", 100], ["findingsBySeverity.pre_existing", 17]]);
    expect(view.tiles.find(tile => tile.metric === "noiseRate")).toMatchObject({ value: "25 %", raw: 0.25 });
    expect(view.tiles.find(tile => tile.metric === "timeToHumanDecisionSeconds.median")?.value).toBe("1.5 h");
  });
  it("turns guardrails warn above zero and shows missing data honestly", () => {
    const view = metricsView(parseReviewMetrics(metricsFixture({ findingAcceptanceRate: null, guardrails: { revertRate: 0.25, incidentRate: null } })));
    expect(view.guardrails.map(tile => tile.tone)).toEqual(["warn", "gap"]);
    expect(view.tiles[0].value).toBe("bez dat");
    expect(view.tiles[1].value).toBe("bez dat");
  });
  it("rejects malformed documents", () => {
    expect(() => parseReviewMetrics(metricsFixture({ findingsBySeverity: { important: -1, nit: 0, pre_existing: 0 } }))).toThrow();
    expect(() => parseReviewMetrics(metricsFixture({ guardrails: {} }))).toThrow();
  });
  it("formats durations and percentages, counts eval cases and links the export", () => {
    expect([duration(30), duration(600), duration(172800), percent(0.12345)]).toEqual(["30 s", "10 min", "2 d", "12.3 %"]);
    expect(parseEvalCount({ items: [{}, {}] })).toBe(2);
    expect(evalExportUrl("p", "w")).toBe("/api/oporahub/review-evals/export.jsonl?project=p&workspace=w");
  });
});
