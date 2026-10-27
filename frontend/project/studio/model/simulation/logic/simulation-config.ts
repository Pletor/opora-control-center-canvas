// Parametry uzlů enginu `flow-model/1` (začátek prototypu `simulation.mjs`): obecné výchozí hodnoty, popisky a meze,
// složení konfigurace uzlu (`config`), prahová odolnost (`resilienceStep`), validace `config.model` a klíče inspektoru.
import { cacheIntegers } from "./cache-model";
import { cloudBudget, cloudConfig, cloudDefinition, cloudParameterKeys, cloudParameters, cloudProfile } from "./cloud-profiles";
import { gatewayIntegers } from "./gateway-model";
import { monitoringIntegers } from "./monitoring-model";
import { objectStoreIntegers } from "./object-store-model";
import { partitionedIntegers, partitionedParameters } from "./partitioned-model";
import { poolIntegers } from "./pool-model";
import { serverlessIntegers } from "./serverless-model";
import type { ModelConfig, ParameterTable } from "./simulation-types";
import { technologyBudget, technologyConfig, technologyIntegers, technologyParameterKeys, technologyParameters } from "./technology";
import { workflowIntegers } from "./workflow-model";

export const MODEL_VERSION = "flow-model/1";
export const ENGINE_VERSION = "flow-rules/1.18.0";
export const defaults = {
  telemetryRate: 1, rate: 250, capacity: 1000, latencyMs: 12.5, concurrency: 20, replicas: 1, buffer: 2000, hitRatio: .8, staticShare: 0, sqlShare: 1, eventShare: .2,
  writeShare: .2, intervalTicks: 5, windowTicks: 3, fanout: 2, targetUtilization: .7, maxReplicas: 6, failureThreshold: 2, resetTicks: 3,
};
export const parameters: ParameterTable = {
  rate: { label: "Zdroj · jednotek / krok", min: 0, max: 100000 }, capacity: { label: "Kapacita · jednotek / krok", min: 0, max: 100000 },
  latencyMs: { label: "Doba obsluhy (ms)", min: .1, max: 60000 }, concurrency: { label: "Souběžné sloty", min: 1, max: 10000 }, replicas: { label: "Počet replik", min: 1, max: 100 },
  buffer: { label: "Velikost fronty / bufferu", min: 0, max: 1000000 }, hitRatio: { label: "Cache hit ratio (0–1)", min: 0, max: 1 },
  staticShare: { label: "Podíl statických odpovědí (0–1)", min: 0, max: 1 }, sqlShare: { label: "SQL operace na požadavek (0–1)", min: 0, max: 1 },
  eventShare: { label: "Události na požadavek (0–1)", min: 0, max: 1 }, writeShare: { label: "Podíl zápisů (0–1)", min: 0, max: 1 },
  intervalTicks: { label: "Cron · interval kroků", min: 1, max: 1000 }, windowTicks: { label: "Stream · velikost okna v krocích", min: 1, max: 100 },
  fanout: { label: "Příjemců na událost", min: 1, max: 100 }, targetUtilization: { label: "Cílové využití autoscalingu", min: .1, max: 1 },
  maxReplicas: { label: "Maximum replik", min: 1, max: 100 }, failureThreshold: { label: "Breaker · kroky s chybou před otevřením", min: 1, max: 100 },
  resetTicks: { label: "Breaker · otevřeno kroků", min: 1, max: 100 },
};
export const resilienceDefaults = { stressThresholdPct: 70, degradedThresholdPct: 100, crashThresholdPct: 400, crashAfterTicks: 0, recoveryThresholdPct: 60, recoveryTicks: 2 };
export const resilienceKeys = Object.keys(resilienceDefaults);
Object.assign(parameters, {
  stressThresholdPct: { label: "Stress · % kapacity", min: 0, max: 10000 }, degradedThresholdPct: { label: "Degraded · % kapacity", min: 1, max: 10000 },
  crashThresholdPct: { label: "Automatické selhání · % kapacity", min: 1, max: 10000 }, crashAfterTicks: { label: "Selhání po přetížení · kroků (0 = vypnuto)", min: 0, max: 1000 },
  recoveryThresholdPct: { label: "Obnova pod zatížením · % kapacity", min: 0, max: 10000 }, recoveryTicks: { label: "Obnova po nízké zátěži · kroků", min: 1, max: 1000 },
});
parameters.telemetryRate = { label: "Telemetry events per processed request", min: 0, max: 1, step: .01 };
parameters.deadlineMs = { label: "Client · mez odhadu čekání (ms)", min: .1, max: 60000 };
Object.assign(parameters, technologyParameters, cloudParameters);

/** Zadané parametry uzlu (`config.model`); chybějící = žádné přepsání výchozích hodnot. */
export const nodeModel = (node: { config: Record<string, unknown> }): ModelConfig | undefined => node.config.model as ModelConfig | undefined;

/** Úplná konfigurace uzlu: obecné výchozí hodnoty, odolnost, technologický nebo cloudový profil a zadaný `config.model`. */
export function config(node: { type: string; config: Record<string, unknown> }): ModelConfig {
  const model = nodeModel(node), technology = technologyConfig(node.type, model), cloud = cloudConfig(node.type, model);
  return {
    ...defaults, ...resilienceDefaults, deadlineMs: 3000, ...(node.type === "client" ? { capacity: 100000, concurrency: 400 } : {}),
    ...(technology ? { ...technology, capacity: technologyBudget(node.type, technology).capacity, latencyMs: technologyBudget(node.type, technology).latencyMs, concurrency: 1000000 } : {}),
    ...(cloud ? { ...cloud, replicas: cloudBudget(node.type, cloud).replicas, capacity: cloudBudget(node.type, cloud).capacity, latencyMs: cloudBudget(node.type, cloud).latencyMs, concurrency: 1000000 } : {}),
    ...model,
  };
}

/** Automatické selhání po trvalém přetížení a obnova po nízké zátěži; ruční incident má přednost. */
export function resilienceStep(c: ModelConfig, old: ModelConfig, pressurePct: number, manual = false, advance = true) {
  let autoFailed = Boolean(old.autoFailed), overloadTicks = old.overloadTicks || 0, recoveryProgress = old.recoveryProgress || 0;
  if (!c.crashAfterTicks || manual) return { autoFailed: false, overloadTicks: 0, recoveryProgress: 0, autoState: null as string | null };
  if (advance && autoFailed) {
    recoveryProgress = pressurePct <= c.recoveryThresholdPct ? recoveryProgress + 1 : 0;
    if (recoveryProgress >= c.recoveryTicks) { autoFailed = false; overloadTicks = 0; recoveryProgress = 0; }
  } else if (advance) {
    overloadTicks = pressurePct >= c.crashThresholdPct ? overloadTicks + 1 : 0;
    if (overloadTicks >= c.crashAfterTicks) { autoFailed = true; recoveryProgress = 0; }
  }
  return {
    autoFailed, overloadTicks, recoveryProgress,
    autoState: (autoFailed ? (recoveryProgress ? "recovering" : "failed") : pressurePct >= c.degradedThresholdPct ? "degraded" : pressurePct >= c.stressThresholdPct ? "stressed" : null) as string | null,
  };
}

const INTEGER_KEYS = ["concurrency", "replicas", "intervalTicks", "windowTicks", "fanout", "maxReplicas", "failureThreshold", "resetTicks", "crashAfterTicks", "recoveryTicks",
  ...technologyIntegers, ...gatewayIntegers, ...monitoringIntegers, ...workflowIntegers, ...serverlessIntegers, ...cacheIntegers, ...poolIntegers, ...objectStoreIntegers, ...partitionedIntegers];

function checkProfileBounds(type: string, value: ModelConfig, numbersOnly: boolean, message: string): void {
  const c = cloudConfig(type, value)!;
  for (const f of Object.values(cloudDefinition(type)!.sourceConfiguration || {}).flat()) {
    const v = c[f.key];
    if ((numbersOnly ? typeof v === "number" : v !== undefined) && ((f.min !== undefined && v < f.min) || (f.max !== undefined && v > f.max))) throw new Error(message + f.key);
  }
}

/** Ověří `config.model` uzlu typu `type`; chyba = výjimka s českou (nebo pozorovanou anglickou) zprávou. */
export function validateModelConfig(value: unknown, type?: string): void {
  if (value === undefined) return;
  const profile = cloudProfile(type);
  if (profile === "serverless-function") {
    const c = cloudConfig(type!, value as ModelConfig)!;
    if (c.minInstances > c.maxInstances) throw new Error("Minimum instances exceeds maximum");
    checkProfileBounds(type!, value as ModelConfig, false, "Value outside observed serverless bounds: ");
  }
  if (["cache", "connection-pool", "object-store", "partitioned-store"].includes(profile!)) checkProfileBounds(type!, value as ModelConfig, true, "Value outside observed profile bounds: ");
  if (type === "ai-inference" && (value as ModelConfig)?.workingSetMb !== undefined && (value as ModelConfig).workingSetMb < 1) throw new Error("AI working set must remain positive");
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Neplatná konfigurace modelu.");
  for (const [key, v] of Object.entries(value as ModelConfig)) {
    const p = profile === "partitioned-store" ? (partitionedParameters[key] || parameters[key]) : parameters[key];
    if (p?.enum) { if (!p.enum.includes(v)) throw new Error(`Neplatný parametr modelu: ${key}.`); continue; }
    if (!p || typeof v !== "number" || !Number.isFinite(v) || v < p.min! || v > p.max!) throw new Error(`Neplatný parametr modelu: ${key}.`);
    if (INTEGER_KEYS.includes(key) && !Number.isInteger(v)) throw new Error(`${key} musí být celé číslo.`);
  }
}

/** Klíče parametrů, které inspektor u typu ukáže (cloudový profil, technologie, jinak obecná sada podle role). */
export function parameterKeys(type: string): string[] {
  if (cloudParameterKeys(type).length) return cloudParameterKeys(type);
  if (technologyParameterKeys(type).length) return technologyParameterKeys(type);
  const keys = ["capacity", "latencyMs", "concurrency", "replicas"];
  if (type === "client") keys.push("deadlineMs");
  if (["service", "pod", "worker"].includes(type)) keys.push("telemetryRate");
  if (["client", "event-producer", "scheduled-job-cron"].includes(type)) keys.unshift("rate");
  if (["queue", "message-broker", "sync-client", "stream-processor", "postgresql-read-replica"].includes(type)) keys.push("buffer");
  if (["redis", "cdn-edge-cache"].includes(type)) keys.push("hitRatio");
  if (type === "frontend-app") keys.push("staticShare");
  if (["service", "pod", "kubernetes-deployment", "worker"].includes(type)) keys.push("sqlShare", "eventShare");
  if (["postgresql", "object-storage", "partitioned-data-store", "coordination-service"].includes(type)) keys.push("writeShare");
  if (type === "scheduled-job-cron") keys.push("intervalTicks");
  if (type === "stream-processor") keys.push("windowTicks");
  if (type === "realtime-gateway") keys.push("fanout");
  if (type === "kubernetes-deployment") keys.push("targetUtilization", "maxReplicas");
  if (type === "circuit-breaker") keys.push("failureThreshold", "resetTicks");
  return keys;
}
