// Dopředný průchod, část 1 (prototyp `stepSimulation`, začátek smyčky uzlů): incident, nabídka ze zdroje a z příchozích
// vazeb, repliky (autoscaling, serverless, controller Deploymentu), kapacita podle profilu, tlak a automatická odolnost.
import { cloudProfile } from "./cloud-profiles";
import type { Controller } from "./deployment";
import { reconcileDeployment } from "./deployment";
import { monitoringPressure } from "./monitoring-model";
import { evaluateObjectStore } from "./object-store-model";
import { evaluatePartitioned } from "./partitioned-model";
import { evaluatePool } from "./pool-model";
import { scaleServerless, serverlessBudget } from "./serverless-model";
import { config, resilienceStep } from "./simulation-config";
import type { ModelConfig, RunIncident, SimEdge, SimNode } from "./simulation-types";
import { capacity, SOURCES, type StepContext } from "./step-schedule";
import { meshDecision, vectorPressure } from "./technology";

/** Pracovní záznam jednoho uzlu v kroku; části dopředného průchodu ho postupně doplňují. */
export type NodeEval = {
  nodeId: string; node: SimNode; c: ModelConfig; old: ModelConfig; incident: RunIncident | null | undefined; profile: string | undefined;
  managedPool: boolean; managedObject: boolean; managedPartitioned: boolean; managedCache: boolean; serverless: boolean;
  failed: boolean; slow: number; byPort: Record<string, number>; offered: number; replicas: number; serverlessScale: { replicas: number; scaleDownTicks: number } | null;
  controller: Controller | null; meshPlan: ReturnType<typeof meshDecision> | null; partitionedPlan: ModelConfig | null; objectPlan: ModelConfig | null; poolPlan: ModelConfig | null;
  cap: number; outEdges: SimEdge[]; pressurePct: number; resilience: ReturnType<typeof resilienceStep>; processed: number; admitted: number; backlog: number; rejected: number;
  internal: string; circuit: string; openUntil: number; failures: number; inputAcceptance: Record<string, number>; technology: ModelConfig | null; outputs: Record<string, number>;
};

export function prepareNode(ctx: StepContext, nodeId: string): NodeEval {
  const { s, previous, preview, incoming, edges, emitEvent } = ctx;
  const node = ctx.byId.get(nodeId)!, c = config(node), old: ModelConfig = previous.nodes[nodeId] || {};
  let incident: RunIncident | null | undefined = s.incidents[nodeId];
  const profile = cloudProfile(node.type), managedPool = profile === "connection-pool", managedObject = profile === "object-store", managedPartitioned = profile === "partitioned-store";
  let failed = incident?.kind === "crash" || incident?.kind === "recovering";
  const slow = incident?.kind === "slow" ? 5 : 1;
  if (!preview && incident?.kind === "recovering") {
    incident.remaining--;
    if (incident.remaining <= 0) { delete s.incidents[nodeId]; if (managedPool || managedObject) { failed = false; incident = null; } }
  }
  const inFlows = incoming.get(nodeId) || [], byPort: Record<string, number> = {};
  for (const flow of inFlows) byPort[flow.edge.to.portId] = (byPort[flow.edge.to.portId] || 0) + flow.amount;
  const wave = s.variation ? 1 + .2 * Math.sin(s.tick * Math.PI / 10) : 1;
  const source = SOURCES.has(node.type) ? c.rate * s.surge * wave * (node.type === "scheduled-job-cron" ? (s.tick > 0 && s.tick % c.intervalTicks === 0 ? 1 : 0) : 1) : 0;
  let offered = source + inFlows.filter((v) => v.edge.type !== "health").reduce((n, v) => n + v.amount, 0);
  let replicas: number = node.type === "kubernetes-deployment" ? (old.replicas ?? c.replicas) : c.replicas;
  // Deployment bez definice šablony škáluje repliky podle využití předchozího kroku (starší pravidlo prototypu).
  if (!preview && node.type === "kubernetes-deployment" && !node.deployment && !failed && previous.tick > 0 && old.utilization !== undefined) {
    if (old.utilization > c.targetUtilization) replicas = Math.min(Math.max(c.replicas, c.maxReplicas), replicas + 1);
    else if (old.utilization < c.targetUtilization * .45) replicas = Math.max(c.replicas, replicas - 1);
  }
  const serverless = profile === "serverless-function", serverlessScale = serverless ? scaleServerless(c, old, !preview, failed) : null;
  if (serverlessScale) replicas = serverlessScale.replicas;
  const controller = node.deployment ? reconcileDeployment(node, s.controllers![nodeId], { offered, tick: !preview, immediate: preview, failed, slow }) : null;
  if (controller) {
    s.controllers![nodeId] = controller;
    replicas = controller.ready; offered = controller.offered;
    for (const event of controller.events) emitEvent(nodeId, event.kind, event.message);
  }
  const meshPlan = node.type === "service-mesh" ? meshDecision(c, old, preview) : null;
  const partitionedPlan = managedPartitioned ? evaluatePartitioned(c, offered, { tick: s.tick, capacityFactor: 1 / slow }) : null;
  const objectPlan = managedObject ? evaluateObjectStore(c, offered, { capacityFactor: 1 / slow }) : null, managedCache = profile === "cache";
  const poolPlan = managedPool ? evaluatePool(c, offered, { capacityFactor: 1 / slow }) : null;
  const cap: number = controller ? controller.capacity : partitionedPlan ? partitionedPlan.capacity : objectPlan ? objectPlan.capacity : poolPlan ? poolPlan.capacity
    : managedCache ? c.capacityRps / slow : serverless ? serverlessBudget(c, { replicas, capacityFactor: 1 / slow }).capacity
    : capacity(c, replicas, slow) / (meshPlan ? 1 + meshPlan.retryRatio : 1);
  const outEdges = edges.filter((e) => e.from.nodeId === nodeId);
  const pressurePct = Math.max(partitionedPlan ? partitionedPlan.pressurePct : objectPlan ? objectPlan.pressurePct : poolPlan ? poolPlan.pressurePct
    : profile === "observability" ? monitoringPressure(c, offered, cap) : cap ? offered / cap * 100 : offered ? 100000 : 0, node.type === "vector-db" ? vectorPressure(c, byPort, slow) : 0);
  const resilience = resilienceStep(c, old, pressurePct, failed, !preview);
  failed = failed || resilience.autoFailed;
  const processed: number = controller ? controller.processed : Math.min(offered, cap);
  return {
    nodeId, node, c, old, incident, profile, managedPool, managedObject, managedPartitioned, managedCache, serverless, failed, slow, byPort, offered, replicas, serverlessScale,
    controller, meshPlan, partitionedPlan, objectPlan, poolPlan, cap, outEdges, pressurePct, resilience, processed, admitted: processed, backlog: 0,
    rejected: Math.max(0, offered - processed), internal: "processing", circuit: old.circuit || "closed", openUntil: old.openUntil || 0, failures: old.failures || 0,
    inputAcceptance: {}, technology: null, outputs: {},
  };
}
