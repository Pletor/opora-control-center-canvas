// Technologické typy (AI inference, identita, service mesh, vektorová DB, CDC) a jejich výchozí parametry (data).
// Převzato z prototypu `technology.mjs`; výpočetní funkce (rozpočty, metriky) patří simulaci a přijdou v etapě S5.
import type { ComponentType } from "./model-types";

export const technologyCatalog: readonly ComponentType[] = [
  {"id":"ai-inference","name":"AI / LLM Inference Gateway","provider":"Generic","group":"Web","category":"Compute","icon":"AI","description":"Token-generation throughput, KV memory and semantic-cache model; no LLM endpoint execution.","sourceStatus":"add-and-ports-observed-ui","ports":[{"id":"http-in","type":"http-request","direction":"input"},{"id":"search-out","type":"search-query","direction":"output"},{"id":"cache-out","type":"cache-command","direction":"output"},{"id":"telemetry-out","type":"telemetry","direction":"output"}]},
  {"id":"auth-provider","name":"Identity / Auth Provider","provider":"Generic","group":"Control","category":"Resilience","icon":"ID","description":"Deterministic verification and rejection model; no actual identity provider or credentials.","sourceStatus":"add-and-ports-observed-ui","ports":[{"id":"http-in","type":"http-request","direction":"input"},{"id":"http-out","type":"http-request","direction":"output"},{"id":"cache-out","type":"cache-command","direction":"output"},{"id":"telemetry-out","type":"telemetry","direction":"output"}]},
  {"id":"service-mesh","name":"Service Mesh / Sidecar","provider":"Generic","group":"Control","category":"Resilience","icon":"M","description":"Explicit deterministic reconstruction; no real service execution.","sourceStatus":"add-and-ports-observed-ui","ports":[{"id":"http-in","type":"http-request","direction":"input"},{"id":"http-out","type":"http-request","direction":"output"},{"id":"health-in","type":"health","direction":"input"},{"id":"telemetry-out","type":"telemetry","direction":"output"}]},
  {"id":"vector-db","name":"Vector Database","provider":"Generic","group":"Data","category":"Storage","icon":"V","description":"Explicit deterministic reconstruction; no real service execution.","sourceStatus":"add-and-ports-observed-ui","ports":[{"id":"query-in","type":"search-query","direction":"input"},{"id":"index-in","type":"event","direction":"input"},{"id":"search-out","type":"search-query","direction":"output"},{"id":"telemetry-out","type":"telemetry","direction":"output"}]},
  {"id":"cdc-connector","name":"CDC Connector (Debezium)","provider":"Generic","group":"Adapter","category":"Messaging","icon":"C","description":"Explicit deterministic reconstruction; no real service execution.","sourceStatus":"add-and-ports-observed-ui","ports":[{"id":"replication-in","type":"sql-replication","direction":"input"},{"id":"record-in","type":"record-command","direction":"input"},{"id":"event-out","type":"event","direction":"output"},{"id":"telemetry-out","type":"telemetry","direction":"output"}]},
];

/** Výchozí parametry modelu podle typu (`technologyConfig` v prototypu). */
export const technologyDefaults: Readonly<Record<string, Readonly<Record<string, number>>>> = {
  "ai-inference": {"maxTokensPerSec":400000,"avgTokensPerRequest":400,"ttftMs":45,"kvCacheLimitMb":24576,"workingSetMb":16384,"semanticCacheHitRate":0.25,"serviceLatencyMs":120},
  "auth-provider": {"verifyCapacityRps":25000,"tokenCacheHitRate":0.85,"jwksLatencyMs":18,"invalidTokenRejectRate":0.02,"mfaChallengeShare":0.05,"serviceLatencyMs":3},
  "service-mesh": {"proxyCapacityRps":35000,"mtlsOverheadMs":2,"retryBudgetPct":20,"outlierThresholdPct":50,"serviceLatencyMs":2},
  "vector-db": {"queryCapacityRps":12000,"upsertCapacityRps":6000,"efSearch":64,"dimensions":1536,"indexMemoryLimitGb":32,"workingSetGb":20,"serviceLatencyMs":8},
  "cdc-connector": {"captureCapacityRps":15000,"snapshotBatchSize":500,"walLagLimit":50000,"transformMs":4,"schemaErrorRate":0.01,"serviceLatencyMs":6},
};

/** Parametry, které musí být celé číslo. */
export const technologyIntegers: readonly string[] = ["efSearch","dimensions","snapshotBatchSize"];

/** Popisek a meze parametrů pro inspektor. */
export const technologyParameters: Readonly<Record<string, { label: string; min: number; max: number }>> = {
  "maxTokensPerSec": {"label":"Decode budget · tokens / step","min":0,"max":1000000000},
  "avgTokensPerRequest": {"label":"Average tokens / request","min":1,"max":1000000},
  "ttftMs": {"label":"Time to first token · model ms","min":0,"max":60000},
  "kvCacheLimitMb": {"label":"KV cache budget · MB","min":1,"max":1000000000},
  "workingSetMb": {"label":"Working set · MB","min":1,"max":1000000000},
  "semanticCacheHitRate": {"label":"Semantic cache hit ratio","min":0,"max":1},
  "serviceLatencyMs": {"label":"Service time · model ms","min":0.1,"max":60000},
  "verifyCapacityRps": {"label":"Verification budget / step","min":0,"max":1000000000},
  "tokenCacheHitRate": {"label":"Token cache hit ratio","min":0,"max":1},
  "jwksLatencyMs": {"label":"JWKS miss cost · model ms","min":0,"max":60000},
  "invalidTokenRejectRate": {"label":"Invalid token rejection ratio","min":0,"max":1},
  "mfaChallengeShare": {"label":"MFA challenge ratio (model overhead)","min":0,"max":1},
  "proxyCapacityRps": {"label":"Proxy attempt budget / step","min":0,"max":1000000000},
  "mtlsOverheadMs": {"label":"mTLS model overhead (ms)","min":0,"max":60000},
  "retryBudgetPct": {"label":"Retry budget %","min":0,"max":100},
  "outlierThresholdPct": {"label":"Outlier failure % (0 disables one-step quarantine)","min":0,"max":100},
  "queryCapacityRps": {"label":"Vector query budget / step","min":0,"max":1000000000},
  "upsertCapacityRps": {"label":"Vector upsert budget / step","min":0,"max":1000000000},
  "efSearch": {"label":"Search breadth (ef)","min":1,"max":4096},
  "dimensions": {"label":"Vector dimensions","min":1,"max":65536},
  "indexMemoryLimitGb": {"label":"Index memory budget GB","min":0.001,"max":1000000},
  "workingSetGb": {"label":"Index working set GB","min":0.001,"max":1000000},
  "captureCapacityRps": {"label":"CDC capture budget / step","min":0,"max":1000000000},
  "snapshotBatchSize": {"label":"Maximum captured changes per step","min":1,"max":1000000},
  "walLagLimit": {"label":"WAL retention (changes)","min":0,"max":1000000000},
  "transformMs": {"label":"Envelope transform model ms","min":0,"max":60000},
  "schemaErrorRate": {"label":"Schema rejection ratio","min":0,"max":1},
};
