import { expect, it } from "vitest";
import type { LogEvent, NodeRun } from "@/shared/flow-editor/logic/flow-types";
import { logRows } from "./log-view";

const event = (seq: number, type: string, payload: unknown, node_run_id: string | null = null, canvas = 1): LogEvent =>
  ({ seq, run_id: "r", node_run_id, ts: "2026-11-03T10:00:00Z", type, payload, canvas });

it("maps log events to rows with their node, text, tone and canvas", () => {
  const runs = [{ id: "n1", node_id: "rozvrh" }] as NodeRun[];
  const rows = logRows([
    event(1, "run.created", { trigger: { source: "schedule", node_id: "rozvrh" } }),
    event(2, "node.queued", { node_id: "rozvrh", attempt: 1 }, "n1"),
    event(3, "node.waiting", { waiting_for: "human", deadline: "2026-11-04" }, "n1"),
    event(4, "node.succeeded", { port: "main", cost_usd: 0.02, model: "haiku" }, "n1"),
    event(5, "node.failed", { error: "boom" }, "cizí"),
    event(6, "canvas.error", { message: "chyba stránky" }, null, 2),
  ], runs);
  expect(rows.map((r) => [r.seq, r.nodeId, r.text, r.tone, r.canvas])).toEqual([
    [1, null, "běh vznikl · schedule · rozvrh", "plain", 1],
    [2, "rozvrh", "ve frontě · pokus 1", "plain", 1],
    [3, "rozvrh", "čeká na human do 2026-11-04", "wait", 1],
    [4, "rozvrh", "hotovo → main · 0.02 $ · haiku", "ok", 1],
    [5, null, "chyba: boom", "bad", 1],
    [6, null, '{"message":"chyba stránky"}', "bad", 2],
  ]);
});
