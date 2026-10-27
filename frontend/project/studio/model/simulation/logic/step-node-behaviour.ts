// Dopředný průchod, část 2 (prototyp `stepSimulation`): chování podle druhu uzlu. Circuit breaker, fronty a stream
// s backlogem, výpadek, a technologické / cloudové kernely (edge cache, balancer, identita, gateway, collector,
// serverless, úložiště, cache, workflow, mesh, vektorová DB, CDC), které přepíšou zpracováno / přijato / odmítnuto.
import { evaluateCache } from "./cache-model";
import { balanceTargets, edgeCacheMetrics } from "./cloud-profiles";
import { gatewayAdmission } from "./gateway-model";
import { monitorTelemetry } from "./monitoring-model";
import { evaluateObjectStore } from "./object-store-model";
import { evaluatePartitioned } from "./partitioned-model";
import { evaluatePool } from "./pool-model";
import { executeServerless } from "./serverless-model";
import { config } from "./simulation-config";
import type { NodeEval } from "./step-node-prepare";
import { capacity, QUEUES, round, type StepContext } from "./step-schedule";
import { authVerification, cdcCapture, vectorEvaluate } from "./technology";
import { createWorkflowState, workflowStep } from "./workflow-model";

const down = (kind: string | undefined) => kind === "crash" || kind === "recovering";

function breakerAndQueues(ctx: StepContext, n: NodeEval): void {
  const { s, preview, byId, emitEvent } = ctx, { node, c, old } = n;
  if (node.type === "circuit-breaker") {
    if (!preview) {
      if (n.circuit === "open") { if (s.tick >= n.openUntil) n.circuit = "half-open"; }
      else if (n.circuit === "half-open" && old.offered > 0) {
        if ((old.dependencySuccess ?? 1) < .5) { n.circuit = "open"; n.openUntil = s.tick + c.resetTicks; } else { n.circuit = "closed"; n.failures = 0; }
      } else if (n.circuit === "closed" && (old.dependencySuccess ?? 1) < .5) {
        n.failures++;
        if (n.failures >= c.failureThreshold) { n.circuit = "open"; n.openUntil = s.tick + c.resetTicks; emitEvent(n.nodeId, "breaker-open", "Breaker otevřen po opakovaném selhání závislosti."); }
      } else if (n.circuit === "closed") n.failures = 0;
    }
    if (n.circuit === "open") { n.processed = 0; n.admitted = 0; n.rejected = n.offered; n.internal = "open"; }
    else if (n.circuit === "half-open") { n.processed = Math.min(n.processed, 1); n.admitted = n.processed; n.rejected = n.offered - n.processed; n.internal = "half-open"; }
  }
  if (QUEUES.has(node.type) || node.type === "stream-processor") {
    const oldBacklog = old.backlog || 0, total = oldBacklog + n.offered;
    const consumers = n.outEdges.filter((e) => ["job", "event", "data", "http-request"].includes(e.type));
    const downstream = consumers.reduce((sum, e) => {
      const target = byId.get(e.to.nodeId)!, fault = s.incidents[target.id]?.kind;
      return sum + (down(fault) ? 0 : capacity(config(target), config(target).replicas, fault === "slow" ? 5 : 1));
    }, 0);
    const dispatch = n.failed ? 0 : Math.min(total, n.cap, downstream);
    n.processed = node.type === "stream-processor" && s.tick % c.windowTicks !== 0 ? 0 : dispatch;
    n.backlog = Math.min(c.buffer, total - n.processed); n.rejected = Math.max(0, total - n.processed - n.backlog); n.admitted = Math.max(0, n.offered - n.rejected);
    n.internal = node.type === "stream-processor" ? "window" : "buffer";
  }
  if (n.failed) {
    n.processed = 0; n.admitted = 0; n.rejected = n.offered; n.backlog = old.backlog || 0; n.internal = n.incident?.kind || "automatic-overload";
    if (n.controller) for (const pod of n.controller.instances) { pod.processed = 0; pod.completed = 0; }
  }
}

function edgeBalancerAuthGateway(ctx: StepContext, n: NodeEval): void {
  const { s, previous, preview, byId, emitEvent } = ctx, { node, c, old, profile, failed } = n;
  if (profile === "edge-cache") n.technology = edgeCacheMetrics(c, n.processed, old);
  if (profile === "load-balancer") {
    const targets = n.outEdges.filter((e) => e.from.portId === "http-out").map((e) => ({
      edgeId: e.id, nodeId: e.to.nodeId,
      available: !down(s.incidents[e.to.nodeId]?.kind) && !previous.nodes[e.to.nodeId]?.autoFailed
        && (!byId.get(e.to.nodeId)!.deployment || s.controllers![e.to.nodeId]?.instances.some((p: { readiness: string }) => p.readiness === "ready")),
    }));
    n.technology = balanceTargets(c, targets, old.technology || {}, preview, failed);
    n.technology.healthSignals = n.byPort["health-in"] || 0;
    if (!n.technology.routable) { n.processed = 0; n.admitted = 0; n.rejected = n.offered; }
  }
  if (node.type === "auth-provider") { n.technology = authVerification(c, n.processed); n.processed = n.technology.accepted; n.admitted = n.processed; n.rejected += n.technology.policyRejected; }
  if (profile === "gateway") {
    const stateLinkUnavailable = n.outEdges.filter((e) => e.from.portId === "cache-out").some((e) => down(s.incidents[e.to.nodeId]?.kind) || previous.nodes[e.to.nodeId]?.autoFailed);
    n.technology = gatewayAdmission(stateLinkUnavailable ? { ...c, stateFailureRate: 1 } : c, n.offered, old.technology || {}, preview, failed);
    n.technology.stateLinkUnavailable = stateLinkUnavailable;
    n.processed = n.technology.accepted; n.admitted = n.processed; n.rejected = n.technology.rejected;
  }
  if (profile === "observability") {
    n.technology = monitorTelemetry(c, n.offered, n.cap, s.tick, old.technology || {}, preview, failed);
    n.processed = n.technology.processed; n.admitted = n.technology.admitted; n.rejected = n.technology.rejected;
    if (!failed && Boolean(old.technology?.alert) !== n.technology.alert)
      emitEvent(n.nodeId, n.technology.alert ? "monitor-alert" : "monitor-clear", n.technology.alert ? "MODEL: collector pressure alert window reached." : "MODEL: collector pressure returned below alert threshold.");
  }
}

function managedKernels(ctx: StepContext, n: NodeEval): void {
  const { s, emitEvent } = ctx, { c, failed, slow } = n;
  if (n.serverless) {
    n.technology = { ...executeServerless(c, n.offered, { replicas: n.replicas, capacityFactor: 1 / slow, failed }), scaleDownTicks: n.serverlessScale!.scaleDownTicks };
    n.processed = n.technology.processed; n.admitted = n.processed; n.rejected = n.technology.rejected;
    if (n.technology.throttled) emitEvent(n.nodeId, "serverless-throttled", `MODEL: throttled ${round(n.technology.throttled)} invocations at configured concurrency ceiling.`);
  }
  if (n.managedPartitioned) {
    n.technology = failed ? evaluatePartitioned(c, n.offered, { tick: s.tick, capacityFactor: 1 / slow, failed: true }) : n.partitionedPlan;
    n.processed = n.technology!.processed; n.admitted = n.processed; n.rejected = n.technology!.rejected; n.internal = "partitions";
  }
  if (n.managedObject) {
    n.technology = failed ? evaluateObjectStore(c, n.offered, { capacityFactor: 1 / slow, failed: true }) : n.objectPlan;
    n.processed = n.technology!.processed; n.admitted = n.processed; n.rejected = n.technology!.rejected; n.internal = "objects";
  }
  if (n.managedPool) {
    n.technology = failed ? evaluatePool(c, n.offered, { capacityFactor: 1 / slow, failed: true }) : n.poolPlan;
    n.processed = n.technology!.processed; n.admitted = n.processed; n.rejected = n.technology!.rejected; n.internal = "sql-pool";
  }
  if (n.managedCache) {
    n.technology = evaluateCache(c, n.offered, { capacityFactor: 1 / slow, failed });
    n.processed = n.technology.processed; n.admitted = n.processed; n.rejected = n.technology.rejected; n.internal = "cache";
  }
}

function workflowMeshVectorCdc(ctx: StepContext, n: NodeEval): void {
  const { s, preview, emitEvent } = ctx, { node, c, old, failed, slow } = n;
  if (n.profile === "workflow") {
    const t = preview ? structuredClone(old.technology || createWorkflowState())
      : workflowStep(c, { offered: n.offered, capacity: n.cap, tick: s.tick, failed, hasWorker: n.outEdges.some((e) => e.from.portId === "job-out") }, old.technology || {});
    t.configurationPending = preview;
    if (preview) n.offered = old.offered || 0;
    n.technology = t; n.processed = t.dispatched; n.admitted = t.admitted; n.rejected = t.overflow; n.backlog = t.queued + t.held;
    for (const kind of ["retried", "succeeded", "timedOut", "exhausted", "compensated", "canceled"]) if (t[kind]) emitEvent(n.nodeId, "workflow-" + kind, `MODEL: ${kind} ${round(t[kind])} workflow units.`);
  }
  if (n.meshPlan) {
    if (n.meshPlan.ejected && !failed) { n.processed = 0; n.admitted = 0; n.rejected = n.offered; }
    n.technology = { ...n.meshPlan, attempts: n.processed * (1 + n.meshPlan.retryRatio), retries: n.processed * n.meshPlan.retryRatio };
    if (n.meshPlan.ejected && !old.meshEjected) emitEvent(n.nodeId, "mesh-quarantine", "MODEL: one-step outlier quarantine; next tick probes again.");
  }
  if (node.type === "vector-db") {
    const t = vectorEvaluate(c, n.byPort, failed ? 0 : n.cap, slow);
    n.technology = t; n.processed = t.queryProcessed + t.indexProcessed; n.admitted = n.processed; n.rejected = n.offered - n.processed;
    n.inputAcceptance = { "query-in": t.queryOffered ? t.queryProcessed / t.queryOffered : 0, "index-in": t.indexOffered ? t.indexProcessed / t.indexOffered : 0 };
  }
  if (node.type === "cdc-connector") {
    const t = cdcCapture(c, n.offered, old.backlog || 0, n.cap, failed);
    n.technology = t; n.processed = t.captured; n.admitted = t.admitted; n.backlog = t.lag; n.rejected = t.admissionRejected;
    if (t.schemaRejected > 0) emitEvent(n.nodeId, "schema-rejection", `MODEL: filtered ${round(t.schemaRejected)} captured changes.`);
    if (t.overflow > 0) emitEvent(n.nodeId, "retention-overflow", `MODEL: lost ${round(t.overflow)} changes outside retention.`);
  }
}

/** Chování uzlu ve stejném pořadí jako prototyp (pořadí rozhoduje, kdo přepíše zpracované množství). */
export function applyBehaviour(ctx: StepContext, n: NodeEval): void {
  breakerAndQueues(ctx, n);
  edgeBalancerAuthGateway(ctx, n);
  managedKernels(ctx, n);
  workflowMeshVectorCdc(ctx, n);
}
