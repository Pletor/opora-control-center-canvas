// Vlastní deterministický tekutinový SQL model (prototyp `pool-model.mjs`), rekonstruovaný z ohraničených pozorování.
// Nespouští SQL dotazy; opakování kvůli zámkům jsou souhrnné ztráty, ne trvalé úlohy.
import { checkCapacityFactor, checkParameters, type KernelOptions } from "./parameter-check";
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const POOL_VERSION = "pool-model/1";
export const poolParameters: ParameterTable = {
  readCapacityRps: { label: "Read capacity / model second", min: 0, max: 1e9 },
  writeCapacityTps: { label: "Write capacity / model second", min: 0, max: 1e9 },
  readRatio: { label: "Configured read share", min: 0, max: 1, step: .01 },
  maxConnections: { label: "Maximum connection slots", min: 1, max: 1e6 },
  readLatencyMs: { label: "Read service duration (model ms)", min: 0, max: 1e6 },
  writeLatencyMs: { label: "Write service duration (model ms)", min: 0, max: 1e6 },
  isolationLevel: { label: "Isolation level", enum: ["read-committed", "repeatable-read", "serializable"] },
  lockContention: { label: "Configured lock contention fraction", min: 0, max: .5, step: .01 },
};
export const poolIntegers = ["maxConnections"];
const ISOLATION: Record<string, number> = { "read-committed": 1, "repeatable-read": 1.25, serializable: 1.6 };

export function poolBudget(c: ModelConfig, { capacityFactor = 1 }: { capacityFactor?: number } = {}) {
  checkParameters(c, poolParameters, poolIntegers, "pool");
  checkCapacityFactor(capacityFactor, "pool");
  const readServiceMs = Math.max(1, c.readLatencyMs), writeServiceMs = Math.max(1, c.writeLatencyMs), weightedMs = c.readRatio * readServiceMs + (1 - c.readRatio) * writeServiceMs;
  const configured = (c.readCapacityRps + c.writeCapacityTps) * capacityFactor, connectionLimit = c.maxConnections * capacityFactor, derived = connectionLimit * 1000 / weightedMs;
  return { readServiceMs, writeServiceMs, weightedMs, configured, connectionLimit, derived, capacity: Math.min(configured, derived), limiter: configured <= derived ? "read-write-ceilings" : "connection-pool" };
}

export function evaluatePool(c: ModelConfig, offered: number, { capacityFactor = 1, failed = false }: KernelOptions = {}) {
  const budget = poolBudget(c, { capacityFactor });
  if (!Number.isFinite(offered) || offered < 0) throw new RangeError("Invalid SQL offered volume");
  const readDemand = offered * c.readRatio, writeDemand = offered - readDemand, readCeiling = c.readCapacityRps * capacityFactor, writeCeiling = c.writeCapacityTps * capacityFactor;
  const boundedRead = Math.min(readDemand, readCeiling), boundedWrite = Math.min(writeDemand, writeCeiling);
  const occupancy = (boundedRead * budget.readServiceMs + boundedWrite * budget.writeServiceMs) / 1000, scale = Math.min(1, budget.connectionLimit / Math.max(1, occupancy));
  const potentialActiveConnections = Math.min(budget.connectionLimit, occupancy * scale);
  const utilization = Math.max(readDemand / Math.max(1, readCeiling), writeDemand / Math.max(1, writeCeiling), budget.connectionLimit ? potentialActiveConnections / budget.connectionLimit : 0);
  const isolationMultiplier = ISOLATION[c.isolationLevel];
  const readServed = failed ? 0 : boundedRead * scale, writeAdmitted = failed ? 0 : boundedWrite * scale, writeRetries = writeAdmitted * c.lockContention * isolationMultiplier;
  const writeCommitted = Math.max(0, writeAdmitted - writeRetries), processed = readServed + writeCommitted, activeConnections = failed ? 0 : potentialActiveConnections;
  const rejected = Math.max(0, offered - processed), readRejected = Math.max(0, readDemand - readServed), writeRejected = Math.max(0, writeDemand - writeAdmitted);
  const connectionRejected = readRejected + writeRejected;
  const u = Math.min(.999, Math.max(0, utilization)), serviceMs = capacityFactor ? c.readLatencyMs / capacityFactor : c.readLatencyMs, waitMs = serviceMs * u / (1 - u), latencyMs = serviceMs + waitMs;
  return {
    modelVersion: POOL_VERSION, ...budget, offered, readDemand, writeDemand, boundedRead, boundedWrite, occupancy, scale, isolationMultiplier, readServed, writeAdmitted,
    writeRetries, writeCommitted, processed, completed: processed, rejected, readRejected, writeRejected, connectionRejected, activeConnections, utilization,
    pressurePct: budget.capacity > 0 ? utilization * 100 : offered ? 1000 : 0, serviceMs, waitMs, latencyMs, unavailable: failed ? offered : 0,
    outputs: (failed ? {} : { "sql-out": processed, "replication-out": writeCommitted }) as Record<string, number>,
  };
}
