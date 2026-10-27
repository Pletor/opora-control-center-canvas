// Zpětný průchod kroku (prototyp `stepSimulation`): přijetí na vazbách podle cíle, zpětný tlak front na úlohy a návrat
// dokončení / zpětného tlaku jen po synchronních závislostech (od listů ke zdrojům). Edge cache, gateway, mesh, CDC
// a Client mají vlastní pravidla dokončení.
import { clientWindow } from "./client-policy";
import { cloudProfile, completeEdgeCache } from "./cloud-profiles";
import { config } from "./simulation-config";
import type { NodeRow, SimEdge } from "./simulation-types";
import { round, SOURCES, SYNCHRONOUS, type StepContext } from "./step-schedule";

/** Přijato na vazbě = nabídka × poměr přijetí cíle (u health vazby dostupnost cíle). */
export function acceptEdges(ctx: StepContext): void {
  const { s, edges } = ctx;
  for (const edge of edges) {
    const target = s.nodes[edge.to.nodeId], flow = s.edges[edge.id];
    const ratio = target.inputAcceptance[edge.to.portId] ?? (edge.type === "health" ? (["failed", "recovering"].includes(target.state) ? 0 : 1) : target.offered ? Math.min(1, target.admitted / target.offered) : 0);
    flow.accepted = flow.offered * ratio; flow.rejected = Math.max(0, flow.offered - flow.accepted);
  }
}

/** Úlohy, které worker odmítl, zůstanou ve frontě, dokud je v bufferu místo; zbytek fronta odmítne. */
export function queueBackpressure(ctx: StepContext): void {
  const { domain, s, edges } = ctx;
  for (const node of domain.nodes.filter((n) => ["queue", "message-broker"].includes(n.type))) {
    const row = s.nodes[node.id], blocked = edges.filter((e) => e.from.nodeId === node.id && e.type === "job").reduce((n, e) => n + s.edges[e.id].rejected, 0);
    const space = Math.max(0, config(node).buffer - row.backlog);
    row.backlog += Math.min(space, blocked); row.processed = Math.max(0, row.processed - blocked); row.completed = row.processed; row.rejected += Math.max(0, blocked - space);
    if (row.backlog > 0 && row.state === "healthy") row.state = "overloaded";
  }
}

function targetRow(ctx: StepContext, e: SimEdge): NodeRow | undefined {
  return ctx.delayed.has(e.id) ? ctx.previous.nodes[e.to.nodeId] : ctx.s.nodes[e.to.nodeId];
}

const completedOn = (ctx: StepContext, group: SimEdge[]) => group.reduce((n, e) => n + ctx.s.edges[e.id].accepted * (targetRow(ctx, e)?.dependencySuccess ?? 1), 0);

function synchronousFactor(ctx: StepContext, nodeId: string, groups: Map<string, SimEdge[]>): number {
  const { s, byId } = ctx, row = s.nodes[nodeId], node = byId.get(nodeId)!, c = config(node);
  let factor = 1;
  for (const [portId, group] of groups) {
    const offered = group.reduce((n, e) => n + s.edges[e.id].offered, 0);
    if (!offered) continue;
    const completed = completedOn(ctx, group);
    let share = node.type === "ai-inference" && portId === "search-out" ? 1 - c.semanticCacheHitRate
      : node.type === "vector-db" && portId === "search-out" ? (row.processed ? row.technology.queryProcessed / row.processed : 0) : 1;
    if (portId === "sql-out") share = row.processed ? (cloudProfile(node.type) === "serverless-function" ? Math.min(1, offered / row.processed) : offered / row.processed) : c.sqlShare;
    if (["frontend-app", "cdn-edge-cache"].includes(node.type) && portId === "http-out") share = node.type === "frontend-app" ? 1 - c.staticShare : 1 - c.hitRatio;
    factor = Math.min(factor, 1 - share + share * completed / offered);
  }
  return factor;
}

function completeNode(ctx: StepContext, nodeId: string): void {
  const { s, previous, preview, edges, byId, emitEvent } = ctx, row = s.nodes[nodeId], node = byId.get(nodeId)!, c = config(node), profile = cloudProfile(node.type);
  const groups = new Map<string, SimEdge[]>();
  for (const edge of edges.filter((e) => e.from.nodeId === nodeId && SYNCHRONOUS.has(e.type) && e.from.portId !== "cache-out")) {
    const group = groups.get(edge.from.portId) || [];
    group.push(edge);
    groups.set(edge.from.portId, group);
  }
  let factor = synchronousFactor(ctx, nodeId, groups);
  if (node.type === "client" && !edges.some((e) => e.from.nodeId === nodeId && e.from.portId === "http-out")) factor = 0;
  if (SOURCES.has(node.type) && node.type !== "client") {
    const outgoing = edges.filter((e) => e.from.nodeId === nodeId), sent = outgoing.reduce((n, e) => n + s.edges[e.id].offered, 0), accepted = outgoing.reduce((n, e) => n + s.edges[e.id].accepted, 0);
    factor = sent ? accepted / sent : 0;
  }
  if (profile === "edge-cache") {
    const origin = groups.get("http-out") || [], originOffered = origin.reduce((n, e) => n + s.edges[e.id].offered, 0);
    const originSuccess = originOffered ? completedOn(ctx, origin) / originOffered : 0;
    row.technology = completeEdgeCache(c, row.technology, { tick: s.tick, processed: row.processed, originConnected: origin.length > 0, originSuccess });
    factor = row.technology.success;
  }
  if (profile === "gateway") {
    const backends = edges.filter((e) => e.from.nodeId === nodeId && e.from.portId === "http-out");
    row.latencyMs = row.technology.latencyMs * (row.slow ? 5 : 1);
    const latency = row.latencyMs + Math.max(0, ...backends.map((e) => targetRow(ctx, e)?.latencyMs || 0));
    row.technology.backendLatencyMs = latency;
    if (!backends.length) factor = 0;
    else if (latency > c.timeoutMs) {
      row.technology.timedOut = row.processed * factor; factor = 0;
      if (row.technology.timedOut) emitEvent(nodeId, "gateway-timeout", `MODEL: direct-backend deadline exceeded (${round(latency)} > ${c.timeoutMs} ms).`);
    }
  }
  if (node.type === "service-mesh") factor = 1 - Math.pow(1 - factor, 1 + (row.technology?.retryRatio || 0));
  if (node.type === "cdc-connector") factor *= 1 - c.schemaErrorRate;
  row.dependencySuccess = Math.max(0, Math.min(1, factor));
  row.completed = profile === "workflow" ? row.technology.succeeded : row.processed * row.dependencySuccess;
  if (node.deployment) {
    const controller = s.controllers![nodeId];
    controller.dependencySuccess = row.dependencySuccess;
    for (const pod of controller.instances) pod.completed = pod.processed * row.dependencySuccess;
  }
  if (node.type === "client" && !["failed", "recovering"].includes(row.state)) {
    const window = clientWindow({
      offered: row.offered, processed: row.processed, completed: row.completed, capacity: row.capacity, baselineMs: row.latencyMs, deadlineMs: c.deadlineMs,
      stressPct: c.stressThresholdPct, degradedPct: c.degradedThresholdPct, recoveryPct: c.recoveryThresholdPct, recoveryTicks: c.recoveryTicks, previous: previous.nodes[nodeId], advance: !preview,
    });
    Object.assign(row, window, { slow: row.slow || window.slow, slowFactor: Math.max(window.slowFactor, Math.round(window.latencyMs / c.latencyMs)) });
  }
  if (row.processed && row.dependencySuccess < .999 && row.state === "healthy") row.state = "degraded";
}

/** Zpětný průchod v obráceném pořadí rozvrhu: každý uzel zná dokončení všech svých synchronních cílů. */
export function backwardPass(ctx: StepContext): void {
  for (const nodeId of [...ctx.order].reverse()) completeNode(ctx, nodeId);
}
