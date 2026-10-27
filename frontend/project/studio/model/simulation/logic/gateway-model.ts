// Vlastní tekutinový model přijetí na API gateway (prototyp `gateway-model.mjs`). Žádný runtime dodavatele ani skutečné
// síťové požadavky.
import type { ModelConfig, ParameterTable } from "./simulation-types";

export const GATEWAY_VERSION = "gateway-model/1";
export const gatewayParameters: ParameterTable = {
  rateLimitRps: { label: "Admission rate / model step", min: 0, max: 1e9 },
  burstCapacity: { label: "Burst reserve", min: 0, max: 1e9 },
  timeoutMs: { label: "Direct-backend deadline (model ms)", min: .1, max: 60000 },
  baseLatencyMs: { label: "Gateway service latency (model ms)", min: 0, max: 60000 },
  overloadLatencyMs: { label: "Latency at full admission rejection (model ms)", min: 0, max: 60000 },
  limiterAlgorithm: { label: "Limiter algorithm", enum: ["token-bucket", "sliding-window"] },
  limiterScope: { label: "Limiter scope", enum: ["global", "keyed"] },
  limiterKeyCount: { label: "Logical key count", min: 1, max: 1000000 },
  limiterShardCount: { label: "State shard count (distribution only)", min: 1, max: 1000000 },
  hotKeyShare: { label: "Additional traffic share on the first key", min: 0, max: 1 },
  stateFailureRate: { label: "Fraction of unavailable limiter state", min: 0, max: 1 },
  outagePolicy: { label: "State outage policy", enum: ["fail-open", "fail-closed"] },
};
export const gatewayIntegers = ["limiterKeyCount", "limiterShardCount"];

type Lane = { accepted: number; tokens: number };

function lane(offered: number, rate: number, burst: number, previous: Lane | undefined, algorithm: string): Lane {
  if (algorithm === "sliding-window") {
    const available = Math.max(0, 2 * rate + burst - (previous?.accepted || 0)), accepted = Math.min(offered, available);
    return { accepted, tokens: 0 };
  }
  const available = rate + Math.min(burst, previous?.tokens ?? burst), accepted = Math.min(offered, available);
  return { accepted, tokens: Math.min(burst, Math.max(0, available - accepted)) };
}

/** Přijetí jedné kroku: horký a studené klíče, rezerva (token bucket) nebo dvoukrokové okno, výpadek stavu limiteru. */
export function gatewayAdmission(c: ModelConfig, offered: number, old: ModelConfig = {}, preview = false, failed = false) {
  const count = c.limiterScope === "keyed" ? c.limiterKeyCount : 1, signature = `${c.limiterAlgorithm}:${c.limiterScope}:${count}`, compatible = old.signature === signature;
  const basis = preview && compatible ? old.basis : compatible ? old.state : undefined;
  const healthy = failed ? 0 : offered * (1 - c.stateFailureRate), hot = count === 1 ? healthy : healthy * (c.hotKeyShare + (1 - c.hotKeyShare) / count);
  const cold = count === 1 ? 0 : healthy * (1 - c.hotKeyShare) / count, rate = c.rateLimitRps / count, burst = c.burstCapacity / count;
  const hotLane = lane(hot, rate, burst, basis?.hot, c.limiterAlgorithm), coldLane = lane(cold, rate, burst, basis?.cold, c.limiterAlgorithm);
  const limited = hotLane.accepted + (count - 1) * coldLane.accepted, bypassed = !failed && c.outagePolicy === "fail-open" ? offered * c.stateFailureRate : 0, accepted = limited + bypassed;
  const activeShards = Math.min(count, c.limiterShardCount), maxShardLoad = hot + Math.max(0, Math.ceil(count / activeShards) - 1) * cold;
  return {
    modelVersion: GATEWAY_VERSION, signature, basis: basis || null, state: failed ? (old.state || null) : { hot: hotLane, cold: coldLane }, accepted,
    rejected: Math.max(0, offered - accepted), limited, bypassed, stateUnavailable: failed ? 0 : offered * c.stateFailureRate, stateLookups: failed ? 0 : offered,
    logicalKeys: count, activeShards, maxShardLoad, tokens: failed ? 0 : hotLane.tokens + (count - 1) * coldLane.tokens,
    latencyMs: c.baseLatencyMs + c.overloadLatencyMs * (offered ? (offered - accepted) / offered : 0), timedOut: 0,
  } as ModelConfig;
}
