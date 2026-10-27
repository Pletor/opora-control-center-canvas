// Číselná rekonstrukce chování Clienta (prototyp `client-policy.mjs`), napasovaná na zaznamenané pokusy. Odhaduje čekání
// ve frontě modelu; není to uplynulý čas HTTP ani řidič síťového timeoutu.
import type { ModelConfig } from "./simulation-types";

export type ClientWindowInput = {
  offered: number; processed: number; completed: number; capacity: number; baselineMs: number; deadlineMs: number;
  stressPct?: number; degradedPct?: number; recoveryPct?: number; recoveryTicks?: number; previous?: ModelConfig; advance?: boolean;
};

export function clientWindow({ offered, processed, completed, capacity, baselineMs, deadlineMs, stressPct = 70, degradedPct = 100, recoveryPct = 60, recoveryTicks = 2, previous = {}, advance = true }: ClientWindowInput) {
  const utilization = capacity > 0 ? offered / capacity : offered ? Infinity : 0;
  const latencyMs = Math.min(deadlineMs, utilization >= 1 ? deadlineMs : baselineMs / (1 - utilization));
  const limited = Math.max(0, offered - processed), dependencyFailure = completed + 1e-7 < processed;
  let state = limited > 1e-7 || dependencyFailure || utilization * 100 >= degradedPct ? "degraded" : utilization * 100 >= stressPct ? "pressured" : "healthy";
  let flowRecovering = false, flowRecoveryProgress = 0;
  if (state === "healthy" && (previous.flowRecovering || ["degraded", "pressured", "overloaded"].includes(previous.state))) {
    flowRecoveryProgress = utilization * 100 <= recoveryPct ? (previous.flowRecoveryProgress || 0) + (advance ? 1 : 0) : 0;
    flowRecovering = flowRecoveryProgress < recoveryTicks;
    if (flowRecovering) state = "recovering";
  }
  const slowFactor = Math.max(1, Math.round(latencyMs / baselineMs));
  return {
    latencyMs, limited, slowFactor, slow: slowFactor > 1, state, flowRecovering, flowRecoveryProgress,
    flowConstraint: limited > 1e-7 ? "concurrency" : dependencyFailure ? "dependency" : state === "pressured" ? "pressure" : flowRecovering ? "recovery" : null,
  };
}
