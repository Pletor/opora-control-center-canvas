// Vlastní tekutinový stavový automat workflow (prototyp `workflow-model.mjs`). Žádné skutečné úlohy, trvalý cloudový
// stav ani rollback transakcí.
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const WORKFLOW_VERSION = "workflow-model/1";
export const workflowParameters: ParameterTable = {
  maxActive: { label: "Maximum active workflow volume", min: 0, max: 1000000 },
  dispatchRps: { label: "Attempt dispatch budget / model step", min: 0, max: 1e9 },
  retryLimit: { label: "Additional attempts before exhaustion", min: 0, max: 100 },
  backoffTicks: { label: "Retry backoff (logical ticks)", min: 0, max: 1000 },
  timeoutTicks: { label: "Workflow age limit (logical ticks)", min: 1, max: 10000 },
  cancellationRate: { label: "Cancel fraction of new arrivals", min: 0, max: 1 },
  preferenceBlockRate: { label: "Initially blocked arrival fraction", min: 0, max: 1 },
  reconciliationRate: { label: "Release fraction of previously blocked work / step", min: 0, max: 1 },
  failurePolicy: { label: "Failed attempt policy", enum: ["retry", "compensate"] },
  timerAuthority: { label: "Clock during workflow outage", enum: ["server", "client"] },
  externalDelayMs: { label: "Minimum result delay (model ms)", min: 0, max: 60000 },
};
export const workflowIntegers = ["maxActive", "retryLimit", "backoffTicks", "timeoutTicks"];

export type WorkflowBatch = ModelConfig & { amount: number; born: number; attempt: number; stage: "queued" | "held" | "inflight"; readyAt: number };
const volume = (batches: WorkflowBatch[]) => batches.reduce((sum, b) => sum + b.amount, 0);
const TOTAL_KEYS = ["accepted", "terminal", "emitted", "dispatched", "succeeded", "timedOut", "compensated", "exhausted", "canceled", "retried"] as const;

export function createWorkflowState(): ModelConfig {
  return {
    modelVersion: WORKFLOW_VERSION, clock: 0, batches: [], totals: Object.fromEntries(TOTAL_KEYS.map((k) => [k, 0])), pendingEvents: 0, eventOut: 0, offered: 0, admitted: 0,
    overflow: 0, canceled: 0, blocked: 0, released: 0, dispatched: 0, succeeded: 0, timedOut: 0, compensated: 0, exhausted: 0, retried: 0, terminal: 0, active: 0, queued: 0,
    held: 0, inflight: 0, hasWorker: false, feedback: 0,
  };
}

export type WorkflowInput = { offered?: number; capacity?: number; feedback?: number; tick?: number; preview?: boolean; failed?: boolean; hasWorker?: boolean };

export function workflowStep(c: ModelConfig, { offered = 0, capacity = c.dispatchRps, feedback = 0, tick = 0, preview = false, failed = false, hasWorker = false }: WorkflowInput = {}, old: ModelConfig = {}) {
  const basis = preview ? (old.basis || { clock: 0, batches: [], totals: {}, pendingEvents: 0 }) : { clock: old.clock || 0, batches: old.batches || [], totals: old.totals || {}, pendingEvents: old.pendingEvents || 0 };
  const clock = basis.clock + (!failed || c.timerAuthority === "server" ? 1 : 0), outcome = Number.isFinite(feedback) ? Math.max(0, Math.min(1, feedback)) : 0, waiting: WorkflowBatch[] = [];
  let succeeded = 0, timedOut = 0, compensated = 0, exhausted = 0, retried = 0, released = 0;
  for (const original of basis.batches as WorkflowBatch[]) {
    const b = { ...original };
    if (b.stage === "inflight" && b.outcome === null && !b.receipt && tick > b.dispatchTick) b.outcome = outcome;
    if (clock - b.born >= c.timeoutTicks) { timedOut += b.amount; continue; }
    if (!failed && b.stage === "inflight" && b.outcome !== null && clock >= b.readyAt) {
      const successful = b.amount * b.outcome, unsuccessful = Math.max(0, b.amount - successful);
      succeeded += successful;
      if (unsuccessful) {
        if (c.failurePolicy === "compensate") compensated += unsuccessful;
        else if (b.attempt < c.retryLimit) { retried += unsuccessful; waiting.push({ amount: unsuccessful, born: b.born, attempt: b.attempt + 1, stage: "queued", readyAt: clock + c.backoffTicks }); }
        else exhausted += unsuccessful;
      }
      continue;
    }
    if (!failed && b.stage === "held") {
      const ready = b.amount * c.reconciliationRate;
      released += ready;
      if (ready) waiting.push({ amount: ready, born: b.born, attempt: b.attempt, stage: "queued", readyAt: clock });
      if (b.amount - ready > 0) waiting.push({ ...b, amount: b.amount - ready });
      continue;
    }
    waiting.push(b);
  }
  const canceled = failed ? 0 : offered * c.cancellationRate, newWork = failed ? 0 : offered - canceled, acceptedWork = Math.min(newWork, Math.max(0, c.maxActive - volume(waiting)));
  const blocked = acceptedWork * c.preferenceBlockRate, admitted = canceled + acceptedWork, overflow = Math.max(0, offered - admitted);
  if (blocked) waiting.push({ amount: blocked, born: clock, attempt: 0, stage: "held", readyAt: clock });
  if (acceptedWork - blocked > 0) waiting.push({ amount: acceptedWork - blocked, born: clock, attempt: 0, stage: "queued", readyAt: clock });
  let budget = !failed && hasWorker ? Math.max(0, Math.min(c.dispatchRps, capacity)) : 0, dispatched = 0;
  const batches: WorkflowBatch[] = [], delay = Math.max(1, Math.ceil(c.externalDelayMs / 1000));
  for (const b of waiting) {
    if (b.stage === "queued" && b.readyAt <= clock && budget > 0) {
      const amount = Math.min(b.amount, budget);
      budget -= amount; dispatched += amount;
      if (b.amount - amount > 0) batches.push({ ...b, amount: b.amount - amount });
      batches.push({ ...b, amount, stage: "inflight", dispatchTick: tick, readyAt: clock + delay, outcome: null });
    } else batches.push(b);
  }
  const terminal = succeeded + timedOut + compensated + exhausted + canceled, eventOut = failed ? 0 : (basis.pendingEvents || 0) + terminal;
  const pendingEvents = failed ? (basis.pendingEvents || 0) + terminal : 0;
  const delta: Record<string, number> = { accepted: admitted, terminal, emitted: eventOut, dispatched, succeeded, timedOut, compensated, exhausted, canceled, retried };
  const totals = Object.fromEntries(Object.entries(delta).map(([k, value]) => [k, (basis.totals[k] || 0) + value]));
  return {
    modelVersion: WORKFLOW_VERSION, basis, clock, batches, totals, pendingEvents, eventOut, offered, admitted, overflow, canceled, blocked, released, dispatched, succeeded,
    timedOut, compensated, exhausted, retried, terminal, active: volume(batches), queued: volume(batches.filter((b) => b.stage === "queued")),
    held: volume(batches.filter((b) => b.stage === "held")), inflight: volume(batches.filter((b) => b.stage === "inflight")), hasWorker, feedback: outcome,
  } as ModelConfig;
}
