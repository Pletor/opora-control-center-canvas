// Dopředný průchod, část 3 (prototyp `stepSimulation`): výstupy portů podle druhu uzlu. Do výstupu se zapisuje jen port,
// ze kterého vede použitelná vazba; ruční přepisy výstupů (`config.outputOverrides`, šablona Deploymentu a lokální
// přepis Podu) mají přednost před vypočtenou hodnotou.
import { componentType } from "../../logic/catalog";
import type { ModelConfig } from "./simulation-types";
import type { NodeEval } from "./step-node-prepare";
import { SOURCES } from "./step-schedule";
import { aiMetrics } from "./technology";

/** Vedlejší efekt cache-aside: dotazy na cache; zásahy vyrovná až `settleCacheReceipts` ze skutečných potvrzenek. */
function cacheSideEffectPlan(n: NodeEval) {
  const links = n.outEdges.filter((e) => e.from.portId === "cache-out"), overrides = n.node.config.outputOverrides as ModelConfig | undefined;
  const queries = n.processed > 0 ? (n.serverless ? (overrides?.["cache-out"] ?? n.processed) : n.processed) : 0;
  const hits = Math.min(n.processed, 0);
  return { cacheQueries: links.length ? queries : 0, cacheHits: hits, cacheFallback: Math.max(0, n.processed - hits) };
}

const SERVICE_LIKE = ["service", "pod", "kubernetes-deployment", "worker"];

function typedOutputs(n: NodeEval, put: (port: string, amount: number) => void): void {
  const { node, c, processed, profile } = n, t = n.technology!;
  if (n.managedPartitioned || n.managedObject || n.managedPool) {
    for (const [key, value] of Object.entries(t.outputs as Record<string, number>)) put(key, value);
    n.internal = n.managedPartitioned ? "partitions" : n.managedObject ? "objects" : "sql-pool";
  } else if (profile === "edge-cache") { put("http-out", t.originRequests); n.internal = "edge-cache"; }
  else if (profile === "load-balancer") { put("http-out", processed); n.internal = t.routable ? "health-routing" : "no-backends"; }
  else if (profile === "gateway") { put("http-out", processed); put("cache-out", t.stateLookups); put("record-out", processed); n.internal = "admission-policy"; }
  else if (profile === "observability") { put("health-out", t.health); n.internal = t.alert ? "collector-alert" : "collector-sampling"; }
  else if (profile === "workflow") {
    put("job-out", t.dispatched); put("event-out", t.eventOut); put("record-out", t.eventOut); put("telemetry-out", t.dispatched);
    n.internal = t.configurationPending ? "workflow-committed" : t.held ? "workflow-preferences" : t.queued ? "workflow-waiting" : "workflow-dispatch";
  } else if (n.serverless) {
    Object.assign(t, cacheSideEffectPlan(n));
    put("sql-out", t.cacheFallback); put("cache-out", processed); put("record-out", processed); put("data-out", processed); put("event-out", processed); put("telemetry-out", t.telemetry);
    n.internal = "serverless-execution";
  } else if (node.type === "service-mesh") { put("http-out", t.attempts); put("telemetry-out", t.attempts); n.internal = t.ejected ? "mesh-quarantine" : "mesh-proxy"; }
  else if (node.type === "vector-db") { put("search-out", t.queryProcessed); put("telemetry-out", processed); n.internal = "vector-index"; }
  else if (node.type === "cdc-connector") { put("event-out", t.emitted); put("telemetry-out", processed); n.internal = "cdc-capture"; }
  else if (node.type === "auth-provider") { put("http-out", processed); put("cache-out", t.verified); put("telemetry-out", t.verified); n.internal = "auth-gate"; }
  else if (node.type === "ai-inference") { const metrics = aiMetrics(c, processed); put("search-out", metrics.decodedRequests); put("cache-out", processed); put("telemetry-out", processed); n.internal = "token-stream"; }
  else genericOutputs(n, put);
}

function genericOutputs(n: NodeEval, put: (port: string, amount: number) => void): void {
  const { node, c, processed, byPort, old } = n;
  if (SOURCES.has(node.type)) put(node.type === "client" ? "http-out" : "event-out", processed);
  else if (["frontend-app", "cdn-edge-cache"].includes(node.type)) {
    const local = node.type === "cdn-edge-cache" ? c.hitRatio : c.staticShare;
    put("http-out", processed * (1 - local)); n.internal = node.type === "cdn-edge-cache" ? "cache" : "assets";
  } else if (SERVICE_LIKE.includes(node.type)) {
    const cachePlan = cacheSideEffectPlan(n);
    put("cache-out", processed); put("sql-out", cachePlan.cacheFallback * c.sqlShare); put("event-out", processed * c.eventShare); put("record-out", processed);
    put("search-out", processed); put("data-out", processed); put("telemetry-out", processed * c.telemetryRate); n.internal = "slots";
  } else if (["queue", "message-broker"].includes(node.type)) { put("job-out", processed); n.internal = "buffer"; }
  else if (node.type === "sync-client") { put("http-out", processed); put("event-out", processed); put("data-out", processed); put("search-out", processed); }
  else if (node.type === "postgresql") { put("sql-out", processed); put("replication-out", processed * c.writeShare); n.internal = "database"; }
  else if (node.type === "postgresql-read-replica") {
    const repl = byPort["replication-in"] || 0, queries = byPort["sql-in"] || 0, failed = n.failed;
    const total = (old.backlog || 0) + repl, applied = failed ? 0 : Math.min(total, n.cap), overflow = failed ? repl : Math.max(0, total - applied - c.buffer);
    n.backlog = failed ? (old.backlog || 0) : Math.min(c.buffer, total - applied);
    const queryProcessed = failed ? 0 : Math.min(queries, n.cap), replAccepted = failed ? 0 : Math.max(0, repl - overflow);
    n.processed = applied + queryProcessed; n.admitted = queryProcessed + replAccepted; n.rejected = n.offered - n.admitted;
    n.technology = { modelVersion: "replica-receipt/1", received: repl, applied, queryProcessed, lag: n.backlog };
    n.inputAcceptance = { "replication-in": repl ? replAccepted / repl : 0, "sql-in": queries ? queryProcessed / queries : 0 };
    put("sql-out", queryProcessed); n.internal = "replication";
  } else if (node.type === "redis") n.internal = "cache";
  else if (node.type === "api-adapter") { put("http-out", processed); put("result-out", processed); n.internal = "adapter"; }
  else if (node.type === "external-provider") { put("result-out", processed); n.internal = "adapter"; }
  else if (node.type === "host-policy-gate") { put("request-out", processed); n.internal = "gate"; }
  else if (node.type === "analytical-store") { put("query-result-out", Math.min(processed, byPort["query-in"] || 0)); put("telemetry-out", processed); n.internal = "database"; }
  else if (node.type === "realtime-gateway") { put("event-out", processed * c.fanout); put("telemetry-out", processed); n.internal = "fanout"; }
  else if (node.type === "stream-processor") { put("event-out", processed); put("data-out", processed); put("search-out", processed); put("telemetry-out", processed); }
  else if (node.type === "workflow-orchestrator") { put("job-out", processed); put("event-out", processed); put("record-out", processed); put("telemetry-out", processed); n.internal = "workflow"; }
  else if (node.type === "partitioned-data-store") { put("cdc-out", processed * c.writeShare); put("telemetry-out", processed); n.internal = "partitions"; }
  else if (node.type === "coordination-service") { put("event-out", processed * c.writeShare); put("telemetry-out", processed); n.internal = "compare-set"; }
  else if (node.type === "search-ranking-index") { put("search-out", Math.min(processed, byPort["query-in"] || 0)); put("telemetry-out", processed); n.internal = "index"; }
  else if (node.type === "geo-index") { put("telemetry-out", processed); n.internal = "spatial"; }
  else if (node.type === "monitoring") { put("health-out", processed); n.internal = "telemetry"; }
  else if (node.type === "object-storage") { put("event-out", processed * c.writeShare); n.internal = "objects"; }
  else if (node.type === "etl-job") { put("event-out", processed); n.internal = "batch"; }
  else {
    for (const port of componentType(node.type)!.ports.filter((p) => p.direction === "output")) put(port.id, processed);
    n.internal = node.type === "circuit-breaker" ? "breaker" : "routing";
  }
}

export function applyOutputs(n: NodeEval): void {
  const has = (port: string) => n.outEdges.some((e) => e.from.portId === port);
  const put = (port: string, amount: number) => { if (has(port)) n.outputs[port] = Math.max(0, amount); };
  typedOutputs(n, put);
  const { node, controller, processed } = n;
  if ((n.serverless || n.managedObject || n.managedPartitioned) && !n.failed && processed > 0)
    for (const [port, amount] of Object.entries((node.config.outputOverrides as Record<string, number> | undefined) || {})) put(port, amount);
  if (controller) {
    put("telemetry-out", processed * node.deployment!.telemetryShare);
    for (const port of ["sql-out", "cache-out", "telemetry-out"]) if (has(port) && controller.instances.some((p) => p.overrides[port] !== undefined)) {
      const base = n.outputs[port] || 0, total = controller.instances.reduce((sum, p) => sum + p.processed, 0);
      put(port, controller.instances.reduce((sum, p) => sum + (p.processed > 0 ? (p.overrides[port] ?? (total ? base * p.processed / total : 0)) : 0), 0));
    }
  }
  if (controller && processed > 0) for (const [port, amount] of Object.entries(node.deployment!.outputOverrides || {})) put(port, amount);
}
