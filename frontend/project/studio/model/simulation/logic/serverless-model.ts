// Vlastní tekutinový model serverless funkce (prototyp `serverless-model.mjs`). Žádné cloudové API a žádné tvrzení
// o shodě s enginem TechViz.
import { checkParameters } from "./parameter-check";
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const SERVERLESS_VERSION = "serverless-model/1";
export const serverlessParameters: ParameterTable = {
  reservedConcurrency: { label: "Reserved instance ceiling", min: 1, max: 1e6, step: 1 },
  instanceConcurrency: { label: "Concurrent invocations per instance", min: 1, max: 1000, step: 1 },
  coldStartLatencyMs: { label: "Cold-start initialization (model ms)", min: 0, max: 1e6, step: 5 },
  coldStartShare: { label: "Configured cold invocation fraction", min: 0, max: 1, step: .01 },
  memoryMb: { label: "Allocated memory / model CPU share (MB)", min: 128, max: 1048576, step: 128 },
  serviceLatencyMs: { label: "Warm execution duration (model ms)", min: 1, max: 1e6, step: 1 },
  telemetryRate: { label: "Telemetry events per completed invocation", min: 0, max: 1, step: .01 },
};
export const serverlessScaleParameters: ParameterTable = {
  minInstances: { label: "Minimum logical workload replicas", min: 1, max: 1000 },
  maxInstances: { label: "Maximum logical workload replicas", min: 1, max: 1000 },
  autoscaleTargetPct: { label: "Logical replica target pressure (%)", min: 1, max: 100 },
  autoscaleScaleDownTicks: { label: "Low-pressure steps before removing one replica", min: 1, max: 1000 },
};
export const serverlessIntegers = ["reservedConcurrency", "instanceConcurrency", "memoryMb", "minInstances", "maxInstances", "autoscaleScaleDownTicks"];

/** Logické repliky funkce podle tlaku předchozího kroku (nad cílem +1, pod polovinou cíle −1 po okně kroků). */
export function scaleServerless(c: ModelConfig, old: ModelConfig = {}, advance = true, failed = false) {
  const minimum = c.minInstances ?? 1, maximum = c.maxInstances ?? 1, target = c.autoscaleTargetPct ?? 70, window = c.autoscaleScaleDownTicks ?? 3;
  if (minimum > maximum) throw new RangeError("Minimum logical instances exceeds maximum");
  let replicas = Math.min(maximum, Math.max(minimum, old.replicas ?? minimum)), scaleDownTicks = old.technology?.scaleDownTicks || 0;
  if (advance && !failed && old.pressurePct !== undefined) {
    if (old.pressurePct > target) { replicas = Math.min(maximum, replicas + 1); scaleDownTicks = 0; }
    else if (old.pressurePct < target * .5) { scaleDownTicks++; if (scaleDownTicks >= window) { replicas = Math.max(minimum, replicas - 1); scaleDownTicks = 0; } }
    else scaleDownTicks = 0;
  }
  return { replicas, scaleDownTicks };
}

export function serverlessBudget(c: ModelConfig, { replicas = 1, capacityFactor = 1 }: { replicas?: number; capacityFactor?: number } = {}) {
  checkParameters(c, serverlessParameters, serverlessIntegers, "serverless");
  if (!Number.isInteger(replicas) || replicas < 1 || replicas > 1000 || !Number.isFinite(capacityFactor) || capacityFactor < 0 || capacityFactor > 1)
    throw new RangeError("Invalid serverless runtime budget");
  const meanDurationMs = c.serviceLatencyMs + c.coldStartLatencyMs * c.coldStartShare, cpuShare = c.memoryMb / 1024, instanceBudget = c.instanceConcurrency * cpuShare * 1000 / meanDurationMs;
  return { meanDurationMs, cpuShare, instanceBudget, maximumInstances: c.reservedConcurrency * replicas, capacity: instanceBudget * c.reservedConcurrency * replicas * capacityFactor };
}

export function executeServerless(c: ModelConfig, offered: number, { replicas = 1, capacityFactor = 1, failed = false }: { replicas?: number; capacityFactor?: number; failed?: boolean } = {}) {
  if (!Number.isFinite(offered) || offered < 0) throw new RangeError("Invalid serverless offered workload");
  const budget = serverlessBudget(c, { replicas, capacityFactor }), effectiveCapacity = failed ? 0 : budget.capacity, processed = Math.min(offered, effectiveCapacity);
  const rejected = offered - processed, effectiveInstanceBudget = budget.instanceBudget * capacityFactor;
  const activeInstances = failed ? 0 : Math.min(budget.maximumInstances, Math.max(replicas, effectiveInstanceBudget ? Math.ceil(processed / effectiveInstanceBudget) : 0));
  const coldInvocations = processed * c.coldStartShare;
  return {
    modelVersion: SERVERLESS_VERSION, ...budget, effectiveCapacity, offered, processed, completed: processed, rejected, throttled: failed ? 0 : rejected,
    unavailable: failed ? rejected : 0, activeInstances, coldInvocations, warmInvocations: processed - coldInvocations,
    latencyMs: capacityFactor ? budget.meanDurationMs / capacityFactor : budget.meanDurationMs, utilization: budget.capacity ? processed / budget.capacity : 0,
    pressurePct: budget.capacity ? offered / budget.capacity * 100 : offered ? 100000 : 0, telemetry: processed * c.telemetryRate,
  };
}
