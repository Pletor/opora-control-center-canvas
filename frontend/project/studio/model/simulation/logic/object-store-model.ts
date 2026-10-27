// Vlastní tekutinový model objektového úložiště (prototyp `object-store-model.mjs`) z ohraničených pozorování zdroje.
// Žádný upload, trvalé uložení, skutečné ACL ani ověření backendu se neprovádí.
import { checkCapacityFactor, checkParameters, type KernelOptions } from "./parameter-check";
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const OBJECT_STORE_VERSION = "object-store-model/1";
export const objectStoreParameters: ParameterTable = {
  requestCapacityRps: { label: "Request ceiling / model second", min: 0, max: 1e9 },
  objectSizeMb: { label: "Average object size (model MB)", min: .01, max: 1e6, step: .1 },
  egressBandwidthMbps: { label: "Egress bandwidth budget (model Mbps)", min: 0, max: 1e9 },
  firstByteLatencyMs: { label: "Base time to first byte (model ms)", min: 1, max: 1e6 },
  accessMode: { label: "Configured access mode", enum: ["public", "signed", "private"] },
  multipartPartSizeMb: { label: "Aggregate part size (model MB)", min: 0, max: 1e6 },
  verificationFailureRate: { label: "Part verification failure fraction (diagnostic)", min: 0, max: 1, step: .01 },
  aclRejectRate: { label: "Access rejection fraction (diagnostic)", min: 0, max: 1, step: .01 },
  failedPartRetryLimit: { label: "Failed-part retry limit (diagnostic)", min: 0, max: 1000 },
};
export const objectStoreIntegers = ["failedPartRetryLimit"];

export function objectStoreBudget(c: ModelConfig, { capacityFactor = 1 }: { capacityFactor?: number } = {}) {
  checkParameters(c, objectStoreParameters, objectStoreIntegers, "object-store");
  checkCapacityFactor(capacityFactor, "object-store");
  const sizeMb = Math.max(.01, c.objectSizeMb), configured = c.requestCapacityRps * capacityFactor, derived = c.egressBandwidthMbps * capacityFactor / (sizeMb * 8);
  return { sizeMb, configured, derived, capacity: Math.min(configured, derived), limiter: configured <= derived ? "request-ceiling" : "egress-bandwidth" };
}

export function evaluateObjectStore(c: ModelConfig, offered: number, { capacityFactor = 1, failed = false }: KernelOptions = {}) {
  const budget = objectStoreBudget(c, { capacityFactor });
  if (!Number.isFinite(offered) || offered < 0) throw new RangeError("Invalid object-store offered volume");
  const processed = failed ? 0 : Math.min(offered, budget.capacity), rejected = Math.max(0, offered - processed), utilization = offered / Math.max(1, budget.capacity);
  const partSizeMb = Math.max(.01, c.multipartPartSizeMb), parts = Math.ceil(processed * budget.sizeMb / partSizeMb), verificationFailures = parts * c.verificationFailureRate;
  const retriedParts = Math.min(verificationFailures, parts * c.failedPartRetryLimit), verifiedParts = Math.max(0, parts - verificationFailures);
  const accessRejected = processed * c.aclRejectRate + (c.accessMode === "private" ? processed * .1 : 0), accessAccepted = Math.max(0, processed - accessRejected);
  const egressMbps = processed * budget.sizeMb * 8, retransmittedBytesMb = retriedParts * partSizeMb;
  const firstByteEstimateMs = c.firstByteLatencyMs * (1 + Math.max(0, offered / Math.max(1, budget.capacity) - 1));
  const u = Math.min(.999, Math.max(0, utilization)), serviceMs = capacityFactor ? c.firstByteLatencyMs / capacityFactor : c.firstByteLatencyMs, waitMs = serviceMs * u / (1 - u);
  const latencyMs = serviceMs + waitMs;
  return {
    modelVersion: OBJECT_STORE_VERSION, ...budget, offered, processed, admitted: processed, rejected, objectsServed: processed, egressMbps, parts, verificationFailures,
    retriedParts, verifiedParts, retransmittedBytesMb, accessRejected, accessAccepted, firstByteEstimateMs, utilization,
    pressurePct: budget.capacity > 0 ? utilization * 100 : offered ? 1000 : 0, serviceMs, waitMs, latencyMs, unavailable: failed ? offered : 0,
    diagnosticPoliciesOnly: true, persistenceVerified: false, outputs: (failed ? {} : { "event-out": processed }) as Record<string, number>,
  };
}
