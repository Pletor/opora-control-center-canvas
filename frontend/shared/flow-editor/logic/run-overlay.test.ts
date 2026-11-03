import { describe, expect, it } from "vitest";
import type { NodeRun, Stall } from "./flow-types";
import { edgeLabel, formatCost, formatDuration, formatTokens, runOverlay } from "./run-overlay";

const run = (id: string, node_id: string, attempt: number, status: NodeRun["status"], extra: Partial<NodeRun> = {}): NodeRun =>
  ({ id, run_id: "r", node_id, attempt, status, ...extra });

describe("run overlay on the canvas", () => {
  it("takes the latest attempt, waiting reason and stall", () => {
    const stall: Stall = { ...run("b2", "jev", 2, "running"), workflow_version_id: "v", reason: "Uzel běží bez heartbeatu." };
    const overlay = runOverlay([run("b1", "jev", 1, "failed"), run("b2", "jev", 2, "running"), run("c", "ok", 1, "waiting", { waiting_for: "human", deadline: "2026-11-04" })], [stall]);
    expect(overlay.get("jev")).toMatchObject({ status: "running", attempt: 2, stall: "Uzel běží bez heartbeatu." });
    expect(overlay.get("ok")).toMatchObject({ status: "waiting", waitingFor: "human", deadline: "2026-11-04", stall: null });
  });
  it("labels main edges with tokens, cost and duration of the finished source", () => {
    const overlay = runOverlay([run("a", "srdce", 1, "succeeded", { tokens_in: 1000, tokens_out: 234, cost_usd: 0.042,
      started_at: "2026-11-03T10:00:00Z", ended_at: "2026-11-03T10:00:03.100Z" }), run("b", "jev", 1, "running")]);
    const edge = { id: "e", source_node: "srdce", source_port: "main", target_node: "x", target_port: "main", kind: "main" as const };
    expect(edgeLabel(edge, overlay)).toBe("1,2k tok · 0,042 $ · 3,1 s");
    expect(edgeLabel({ ...edge, source_node: "jev" }, overlay)).toBe("");
    expect(edgeLabel({ ...edge, kind: "model" }, overlay)).toBe("");
  });
  it("formats numbers the Czech way", () => {
    expect(formatTokens(12)).toBe("12 tok");
    expect(formatCost(1.5)).toBe("1,50 $");
    expect(formatDuration(250)).toBe("250 ms");
    expect(formatDuration(180_000)).toBe("3 min");
  });
});
