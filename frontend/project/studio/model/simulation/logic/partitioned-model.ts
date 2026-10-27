// Vlastní tekutinový model rozděleného úložiště záznamů (prototyp `partitioned-model.mjs`) z ponechaných pozorování.
// Žádné záznamy, fyzické oddíly, trvalý CDC log, distribuovaný konsenzus ani snapshoty se neprovádějí.
import { checkCapacityFactor, checkParameters, type KernelOptions } from "./parameter-check";
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const PARTITIONED_VERSION = "partitioned-model/1";
export const partitionedParameters: ParameterTable = {
  capacityRps: { label: "Configured record operations / model second", min: 0, max: 1e9 },
  readRatio: { label: "Configured read share", min: 0, max: 1, step: .01 },
  replicationFactor: { label: "Configured replication factor", min: 0, max: 1000 },
  partitionCount: { label: "Logical partitions (diagnostic)", min: 1, max: 1e6 },
  hotKeyShare: { label: "Hot-key share (diagnostic)", min: 0, max: 1, step: .01 },
  conditionalConflictRate: { label: "Conditional conflict fraction", min: 0, max: 1, step: .01 },
  consistencyMode: { label: "Consistency reduction", enum: ["one", "quorum", "all"] },
  idAllocationMode: { label: "ID allocation diagnostics", enum: ["hash", "atomic-counter"] },
  allocationRangeSize: { label: "Allocation batch size (diagnostic)", min: 0, max: 1e9 },
  snapshotIntervalTicks: { label: "Snapshot interval (diagnostic model ticks)", min: 0, max: 1e9 },
  serviceLatencyMs: { label: "Record service duration (model ms)", min: 0, max: 1e6 },
};
export const partitionedIntegers = ["replicationFactor", "partitionCount", "allocationRangeSize", "snapshotIntervalTicks"];

export function partitionedBudget(c: ModelConfig, { capacityFactor = 1 }: { capacityFactor?: number } = {}) {
  checkParameters(c, partitionedParameters, partitionedIntegers, "partitioned-store");
  checkCapacityFactor(capacityFactor, "partitioned-store");
  const readRatio = c.readRatio, replicationFactor = Math.max(1, c.replicationFactor), partitionCount = Math.max(1, c.partitionCount);
  const quorumCost = 1 + (1 - readRatio) * (replicationFactor - 1) * .25;
  return { readRatio, replicationFactor, partitionCount, quorumCost, capacity: c.capacityRps * capacityFactor / quorumCost };
}

export function evaluatePartitioned(c: ModelConfig, offered: number, { tick = 0, capacityFactor = 1, failed = false }: KernelOptions & { tick?: number } = {}) {
  const budget = partitionedBudget(c, { capacityFactor });
  if (!Number.isFinite(offered) || offered < 0 || !Number.isSafeInteger(tick) || tick < 0) throw new RangeError("Invalid partitioned-store input/tick");
  const processed = failed ? 0 : Math.min(offered, budget.capacity), rejected = Math.max(0, offered - processed), utilization = offered / Math.max(1, budget.capacity);
  const conditionalRejected = processed * c.conditionalConflictRate, consistencyFactor = c.consistencyMode === "one" ? 1 : c.consistencyMode === "all" ? .8 : .9;
  const conditionalAccepted = (processed - conditionalRejected) * consistencyFactor, averagePartitionRps = processed / budget.partitionCount;
  const hottestPartitionRps = averagePartitionRps * (1 + c.hotKeyShare * (budget.partitionCount - 1));
  const snapshotsCreated = failed ? 0 : Math.floor(tick / Math.max(1, c.snapshotIntervalTicks)), operationLogLength = Math.max(0, processed - snapshotsCreated);
  const serviceMs = capacityFactor ? c.serviceLatencyMs / capacityFactor : c.serviceLatencyMs, u = Math.min(.999, Math.max(0, utilization)), waitMs = serviceMs * u / (1 - u);
  const telemetryRate = c.telemetryRate ?? 1;
  if (!Number.isFinite(telemetryRate) || telemetryRate < 0 || telemetryRate > 1) throw new RangeError("Invalid partitioned-store telemetry rate");
  return {
    modelVersion: PARTITIONED_VERSION, ...budget, offered, processed, admitted: processed, rejected, utilization, pressurePct: utilization * 100,
    readDemand: offered * budget.readRatio, writeDemand: offered * (1 - budget.readRatio) * budget.replicationFactor, readServed: processed * budget.readRatio,
    writeAdmitted: processed * (1 - budget.readRatio) / budget.replicationFactor, conditionalRejected, conditionalAccepted, consistencyFactor, averagePartitionRps,
    hottestPartitionRps, allocatedIds: processed,
    allocationCoordinationOps: c.idAllocationMode === "atomic-counter" ? Math.ceil(processed / Math.max(1, c.allocationRangeSize)) : 0,
    allocationCollisions: c.idAllocationMode === "atomic-counter" ? 0 : conditionalRejected, snapshotsCreated, operationLogLength, replayOperations: operationLogLength,
    serviceMs, waitMs, latencyMs: serviceMs + waitMs, partitionLifecycleModeled: false, durableLogVerified: false,
    outputs: (failed ? {} : { "cdc-out": conditionalAccepted, "telemetry-out": processed * telemetryRate }) as Record<string, number>,
  };
}
