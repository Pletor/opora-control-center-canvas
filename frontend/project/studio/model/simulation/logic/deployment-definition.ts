// Definice Kubernetes Deploymentu a zdraví Podu (první polovina prototypu `deployment.mjs`): šablona řízených Podů,
// její validace a prahová pravidla zdraví jedné instance. Vlastní deterministická rekonstrukce, žádné Kubernetes API.
import type { DeploymentDefinition, ModelConfig } from "./simulation-types";

export const DEPLOYMENT_VERSION = "deployment/1";
export const podResilienceDefaults = { stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 3, recoveryThresholdPct: 60, recoveryTicks: 2, latencyCeilingMs: 8000 };
type Field = [label: string, min: number, max: number, integer?: boolean];
export const podResilienceFields: Record<string, Field> = {
  stressThresholdPct: ["Stress threshold (% capacity)", 0, 100], degradedThresholdPct: ["Degraded threshold (% capacity)", 1, 200],
  crashThresholdPct: ["Crash threshold (% capacity)", 100, 400], crashAfterTicks: ["Crash after sustained overload (ticks)", 1, 1000, true],
  recoveryThresholdPct: ["Recovery threshold (% capacity)", 0, 100], recoveryTicks: ["Recovery threshold (ticks)", 1, 1000, true],
  latencyCeilingMs: ["MODEL · maximum odhadu čekání (ms)", .1, 60000],
};

export function deploymentDefinition(templateId: string): DeploymentDefinition {
  return {
    version: DEPLOYMENT_VERSION, templateId, minReplicas: 2, maxReplicas: 4, targetUtilization: .75, downscaleTicks: 3, replacementTicks: 2, readinessTicks: 1,
    podCapacity: 3000, podLatencyMs: 8, podConcurrency: 400, telemetryShare: .01, podResilience: { ...podResilienceDefaults }, outputOverrides: {},
  };
}

export const deploymentFields: Record<string, Field> = {
  minReplicas: ["Minimum replicas", 1, 100, true], maxReplicas: ["Maximum replicas", 1, 100, true], targetUtilization: ["Target utilization", .1, 1],
  downscaleTicks: ["Scale-down stabilization (ticks)", 1, 1000, true], replacementTicks: ["Replacement detection delay (ticks)", 1, 1000, true],
  readinessTicks: ["Pod readiness delay (ticks)", 0, 1000, true], podCapacity: ["Pod configured capacity / krok", 0, 100000],
  podLatencyMs: ["Pod processing time (ms)", .1, 60000], podConcurrency: ["Pod concurrent slots", 1, 10000, true], telemetryShare: ["Telemetry units per completed work", 0, 1],
};

const isObject = (v: unknown): v is ModelConfig => Boolean(v) && typeof v === "object" && !Array.isArray(v);

export function validateDeployment(value: unknown): asserts value is DeploymentDefinition {
  const d = value as ModelConfig;
  if (!d || d.version !== DEPLOYMENT_VERSION || typeof d.templateId !== "string" || !d.templateId || d.templateId.length > 128) throw new Error("Neplatná definice Deploymentu.");
  if (Object.keys(d).some((k) => !["version", "templateId", "podResilience", "outputOverrides", ...Object.keys(deploymentFields)].includes(k))) throw new Error("Neznámý parametr Deploymentu.");
  for (const [key, [, min, max, integer]] of Object.entries(deploymentFields)) {
    const n = d[key];
    if (!Number.isFinite(n) || n < min || n > max || (integer && !Number.isInteger(n))) throw new Error(`Neplatný parametr Deploymentu: ${key}.`);
  }
  if (d.minReplicas > d.maxReplicas) throw new Error("Minimum replik nesmí přesáhnout maximum.");
  if (d.podResilience !== undefined) {
    const r = d.podResilience;
    if (!isObject(r) || Object.keys(r).some((k) => !podResilienceFields[k])) throw new Error("Neplatná odolnost Pod šablony.");
    for (const [key, [, min, max, integer]] of Object.entries(podResilienceFields)) {
      const n = r[key];
      if (!Number.isFinite(n) || n < min || n > max || (integer && !Number.isInteger(n))) throw new Error(`Neplatný parametr Pod Resilience: ${key}.`);
    }
  }
  if (d.outputOverrides !== undefined) {
    const o = d.outputOverrides;
    if (!isObject(o) || Object.entries(o).some(([key, v]) => !["sql-out", "cache-out", "telemetry-out"].includes(key) || !Number.isFinite(v) || v < 0 || v > 100000))
      throw new Error("Neplatný output override controlleru.");
  }
}

/** Zdraví jedné instance Podu z tlaku na její kapacitu: tlak, degradace, nedostupnost po trvalém přetížení, obnova. */
export function podHealth(c: ModelConfig, previous: ModelConfig = {}, offered: number, capacity: number, baselineMs: number, advance = false) {
  const ratio = capacity > 0 ? offered / capacity : offered ? Infinity : 0, pressurePct = Number.isFinite(ratio) ? ratio * 100 : 100000, high = pressurePct >= c.crashThresholdPct;
  const overloadTicks = advance ? (high ? (previous.overloadTicks || 0) + 1 : 0) : (previous.overloadTicks || 0);
  const unavailable = high && (previous.unavailable || c.crashAfterTicks === 1 || overloadTicks >= c.crashAfterTicks);
  let state = unavailable ? "unavailable" : pressurePct >= c.degradedThresholdPct ? "degraded" : pressurePct >= c.stressThresholdPct ? "pressured" : "healthy", recoveryProgress = 0;
  const needsRecovery = previous.unavailable || previous.state === "recovering" || ["pressured", "degraded"].includes(previous.state);
  if (!unavailable && needsRecovery && state === "healthy") {
    recoveryProgress = pressurePct <= c.recoveryThresholdPct ? (previous.recoveryProgress || 0) + (advance ? 1 : 0) : 0;
    if (recoveryProgress < c.recoveryTicks) state = "recovering";
  }
  const ceiling = Math.max(baselineMs, c.latencyCeilingMs), latencyMs = Math.min(ceiling, ratio >= 1 ? ceiling : baselineMs / (1 - ratio)), slowFactor = Math.max(1, Math.round(latencyMs / baselineMs));
  return { state, unavailable, overloadTicks, recoveryProgress, pressurePct, latencyMs, slowFactor, slow: slowFactor > 1 };
}
