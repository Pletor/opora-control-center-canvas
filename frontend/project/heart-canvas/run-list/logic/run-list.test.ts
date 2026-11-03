import { describe, expect, it } from "vitest";
import type { FlowRun, FlowVersion, Stall } from "@/shared/flow-editor/logic/flow-types";
import { runRows, stallRows, timeLabel } from "./run-list";

const versions = [{ id: "v1", n: 1 }, { id: "v2", n: 2 }] as FlowVersion[];
const run = (id: string, version: string, status: FlowRun["status"], extra: Partial<FlowRun> = {}): FlowRun => ({ id, workflow_version_id: version, status,
  trigger: { source: "schedule", node_id: "rozvrh" }, parent_run_id: null, cost_usd: 0, tokens: 0,
  created_at: "2026-11-03T10:00:00Z", updated_at: "2026-11-03T10:00:02Z", ...extra });
const stall = { id: "n1", run_id: "r2", node_id: "srdce", workflow_version_id: "v2", reason: "Uzel běží bez heartbeatu." } as Stall;

describe("run list", () => {
  it("labels runs with version, trigger, duration, cost and stall", () => {
    const rows = runRows([run("r1", "v1", "succeeded", { cost_usd: 0.5 }), run("r2", "v2", "running")], versions, [stall], null, new Date("2026-11-03T12:00:00Z"));
    expect(rows[0]).toMatchObject({ statusLabel: "hotovo", version: "v1", trigger: "schedule · rozvrh", facts: "2,0 s · 0,50 $", stalled: false });
    expect(rows[1]).toMatchObject({ statusLabel: "běží", facts: "", stalled: true });
  });
  it("filters by the shown version", () => {
    expect(runRows([run("r1", "v1", "succeeded"), run("r2", "v2", "failed")], versions, [], "v2").map((r) => r.id)).toEqual(["r2"]);
  });
  it("keeps only stalls of this workflow", () => {
    expect(stallRows([stall, { ...stall, id: "x", workflow_version_id: "cizí" }], versions)).toEqual([
      { id: "n1", runId: "r2", nodeId: "srdce", reason: "Uzel běží bez heartbeatu.", version: "v2" }]);
  });
  it("shows a bare time for today and passes unreadable input through", () => {
    expect(timeLabel("nečas")).toBe("nečas");
    expect(timeLabel("2026-11-03T10:00:00Z", new Date("2026-11-03T10:30:00Z"))).not.toContain("2026");
  });
});
