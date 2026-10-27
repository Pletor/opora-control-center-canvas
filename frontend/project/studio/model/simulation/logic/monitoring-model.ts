// Vlastní deterministický model telemetrie (prototyp `monitoring-model.mjs`), ne backend CloudWatch / Cloud Monitoring / SLS.
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const MONITORING_VERSION = "monitoring-model/1";
export const monitoringParameters: ParameterTable = {
  retentionMinutes: { label: "Retention (model minutes)", min: 0, max: 1440, step: 1 / 60 },
  sampleRate: { label: "Deterministic retained sample fraction", min: 0, max: 1 },
  ingestCapacityRps: { label: "Ingest budget per replica / step", min: 0, max: 1e9 },
  alertThresholdPct: { label: "Alert pressure threshold (%)", min: 0, max: 100000 },
  evaluationWindowTicks: { label: "Consecutive steps before alert", min: 1, max: 10000 },
  cardinalityLimit: { label: "Allowed active series", min: 0, max: 1e9 },
  activeSeries: { label: "Assumed active series", min: 0, max: 1e9 },
  replicaCount: { label: "Collector replicas", min: 1, max: 1000 },
};
export const monitoringIntegers = ["evaluationWindowTicks", "cardinalityLimit", "activeSeries", "replicaCount"];

export function monitoringPressure(c: ModelConfig, offered: number, capacity: number): number {
  return Math.max(capacity ? offered * c.sampleRate / capacity * 100 : offered * c.sampleRate ? 100000 : 0,
    c.cardinalityLimit ? c.activeSeries / c.cardinalityLimit * 100 : c.activeSeries ? 100000 : 0);
}

type Cohort = { tick: number; amount: number };

/** Vzorkování, kardinalita, kapacita, okno alertu a retence kohort v modelovém čase. */
export function monitorTelemetry(c: ModelConfig, offered: number, capacity: number, tick: number, old: ModelConfig = {}, preview = false, failed = false) {
  const basis: { cohorts: Cohort[]; alertTicks: number } = preview ? (old.basis || { cohorts: [], alertTicks: 0 }) : { cohorts: old.cohorts || [], alertTicks: old.alertTicks || 0 };
  const sampled = offered * c.sampleRate, cardinalityRatio = c.activeSeries ? Math.min(1, c.cardinalityLimit / c.activeSeries) : 1, eligible = sampled * cardinalityRatio;
  const processed = failed ? 0 : Math.min(eligible, capacity), sampledOut = failed ? 0 : offered - sampled, admitted = sampledOut + processed;
  const pressurePct = monitoringPressure(c, offered, capacity), alertTicks = failed ? 0 : pressurePct >= c.alertThresholdPct ? basis.alertTicks + 1 : 0;
  const alert = !failed && alertTicks >= c.evaluationWindowTicks;
  const candidates = [...basis.cohorts, ...(processed ? [{ tick, amount: processed }] : [])], cohorts = candidates.filter((batch) => tick - batch.tick < c.retentionMinutes * 60);
  const retained = cohorts.reduce((n, b) => n + b.amount, 0), expired = candidates.reduce((n, b) => n + b.amount, 0) - retained;
  return {
    modelVersion: MONITORING_VERSION, basis, cohorts, offered, sampled, sampledOut, cardinalityDropped: failed ? 0 : sampled - eligible,
    capacityDropped: failed ? 0 : eligible - processed, processed, admitted, rejected: Math.max(0, offered - admitted), pressurePct, alertTicks, alert,
    health: !failed && !alert ? 1 : 0, retained, expired,
  } as ModelConfig;
}
