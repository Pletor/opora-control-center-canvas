import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import type { CompletionEvidence } from "@/editor/canvas/node-card/components/CardEvidence";

export function compactCheckCount(view: CardView, evidence?: CompletionEvidence) {
  const runs = evidence?.checksRun ?? [];
  const total = view.checks?.length || runs.length;
  const passed = new Set(runs.filter((run) => run.exitCode === 0).map((run) => run.checkId)).size;
  return { total, finished: Math.min(passed, total), failed: runs.filter((run) => run.exitCode !== 0).length };
}
