// Controller Kubernetes Deploymentu (druhá polovina prototypu `deployment.mjs`): doporučený počet replik, výměna
// selhaných Podů, readiness, rozdělení zátěže a ruční příkazy. Řízené Pody jsou instance controlleru v běhu simulace,
// ne uzly modelu. Vlastní deterministická rekonstrukce pozorovaného chování, žádné Kubernetes API.
import { podHealth, validateDeployment } from "./deployment-definition";
import type { ModelConfig, SimDomain, SimNode } from "./simulation-types";

export * from "./deployment-definition";

export type Pod = ModelConfig & { id: string; name: string; state: string; readiness: string; overrides: Record<string, number>; offered: number; processed: number; completed: number };
export type Controller = ModelConfig & { instances: Pod[]; nextOrdinal: number; events: { kind: string; message: string; instanceId: string }[] };

function spawn(node: SimNode, state: Controller, ready: boolean): Pod {
  const ordinal = state.nextOrdinal++;
  return {
    id: `${node.id}:pod:${ordinal}`, templateId: node.deployment!.templateId, ordinal, name: `Pod ${ordinal}`, state: ready ? "healthy" : "initializing",
    readiness: ready ? "ready" : "initializing", readyIn: ready ? 0 : node.deployment!.readinessTicks, failedTicks: 0, overrides: {}, offered: 0, processed: 0, completed: 0,
  };
}
const ready = (pod: Pod) => (pod.readiness ? pod.readiness === "ready" : !["failed", "initializing"].includes(pod.state));

export function controllerCounts(state: Controller) {
  return { actual: state.instances.length, ready: state.instances.filter(ready).length, recommended: state.recommended };
}

export function controllerFaults(state: { controllers?: Record<string, Controller> }) {
  return Object.entries(state.controllers || {}).flatMap(([parentId, c]) => c.instances.filter((p) => p.readiness === "unavailable" || p.manualSlow)
    .map((p) => ({ parentId, instanceId: p.id, name: p.name, kind: p.manualSlow ? "slow" : "crash" })));
}

export type ReconcileInput = { offered?: number; tick?: boolean; immediate?: boolean; failed?: boolean; slow?: number };

export function reconcileDeployment(node: SimNode, previous?: Controller, { offered = previous?.externalOffered || 0, tick = false, immediate = !tick, failed = false, slow = 1 }: ReconcileInput = {}): Controller {
  const c = node.deployment!;
  validateDeployment(c);
  const s: Controller = previous ? structuredClone(previous) : { instances: [], nextOrdinal: 1, downscaleProgress: 0, pressure: false, recoveryRemaining: 0, events: [] };
  s.events = []; s.externalOffered = offered;
  const load = Math.max(offered, s.pressure ? c.maxReplicas * c.podCapacity * .9 : 0);
  s.offered = load;
  s.recommended = Math.max(c.minReplicas, Math.min(c.maxReplicas, c.podCapacity ? Math.ceil(load / (c.podCapacity * c.targetUtilization)) : c.maxReplicas));
  if (tick) {
    if (s.recoveryRemaining > 0) s.recoveryRemaining--;
    for (let i = 0; i < s.instances.length; i++) {
      const pod = s.instances[i];
      if (pod.state === "failed") {
        pod.failedTicks++;
        if (pod.failedTicks >= c.replacementTicks) {
          const replacement = spawn(node, s, c.readinessTicks === 0);
          s.instances[i] = replacement;
          s.events.push({ kind: "replacement", message: `${pod.name} → ${replacement.name}`, instanceId: replacement.id });
        }
      } else if (pod.state === "initializing") {
        pod.readyIn = Math.max(0, pod.readyIn - 1);
        if (!pod.readyIn) { pod.state = "healthy"; pod.readiness = "ready"; s.events.push({ kind: "ready", message: `${pod.name} ready`, instanceId: pod.id }); }
      }
    }
  }
  const target = Math.max(c.minReplicas, s.recommended), missing = Math.max(0, target - s.instances.length);
  for (let i = 0; i < missing; i++) {
    const pod = spawn(node, s, !previous || immediate || c.readinessTicks === 0);
    s.instances.push(pod);
    s.events.push({ kind: "scale-up", message: `${pod.name} added`, instanceId: pod.id });
  }
  if (s.instances.length > target) {
    if (tick && ++s.downscaleProgress >= c.downscaleTicks) {
      const removed = s.instances.pop()!;
      s.downscaleProgress = 0;
      s.events.push({ kind: "scale-down", message: `${removed.name} removed`, instanceId: removed.id });
    }
  } else s.downscaleProgress = 0;
  const available = s.instances.filter(ready), share = available.length ? load / available.length : 0;
  for (const pod of s.instances) {
    const factor = slow * (pod.manualSlow ? 5 : 1), perCapacity = Math.min(c.podCapacity / factor, c.podConcurrency * 1000 / (c.podLatencyMs * factor)), usable = ready(pod) && !failed;
    pod.offered = usable ? share : 0; pod.capacity = usable ? perCapacity : 0; pod.processed = usable ? Math.min(share, perCapacity) : 0;
    pod.completed = pod.processed * (s.dependencySuccess ?? 1); pod.utilization = perCapacity ? pod.offered / perCapacity : 0;
    if (!ready(pod)) continue;
    const oldState = pod.health?.state;
    if (c.podResilience) {
      pod.health = podHealth(c.podResilience, pod.health, pod.offered, perCapacity, c.podLatencyMs * factor, tick);
      pod.state = pod.manualSlow && pod.health.state === "healthy" ? "slow" : pod.health.state;
      pod.latencyMs = pod.health.latencyMs; pod.slow = pod.health.slow || factor > 1; pod.slowFactor = Math.max(1, Math.round(pod.latencyMs / c.podLatencyMs));
      if (tick && oldState && oldState !== pod.health.state)
        s.events.push({ kind: "pod-diagnostic", message: `${pod.name}: ${oldState} → ${pod.health.state}; readiness ${pod.readiness}`, instanceId: pod.id });
    } else {
      pod.state = pod.manualSlow ? "slow" : pod.utilization >= 1 ? "degraded" : pod.utilization >= .7 ? "stressed" : "healthy";
      pod.latencyMs = c.podLatencyMs * factor; pod.slow = factor > 1; pod.slowFactor = factor;
    }
  }
  s.capacity = s.instances.reduce((n, p) => n + p.capacity, 0); s.processed = s.instances.reduce((n, p) => n + p.processed, 0); s.rejected = Math.max(0, load - s.processed);
  Object.assign(s, controllerCounts(s));
  return s;
}

export type ControllerCommandKind = "add" | "pressure" | "external" | "crash" | "slow" | "restore";

export function controllerCommand(node: SimNode, previous: Controller | undefined, kind: ControllerCommandKind | string, instanceId?: string): Controller {
  const s = previous ? structuredClone(previous) : reconcileDeployment(node);
  s.events = [];
  if (kind === "add") {
    if (s.instances.length >= node.deployment!.maxReplicas) throw new Error("Dosaženo nastavené maximum replik. Pro další Pod zvyšte Maximum replicas.");
    const pod = spawn(node, s, true);
    s.instances.push(pod);
    s.events.push({ kind: "manual-add", message: `${pod.name} added`, instanceId: pod.id });
  } else if (kind === "pressure") { s.pressure = true; s.recoveryRemaining = 0; }
  else if (kind === "external") { s.pressure = false; s.recoveryRemaining = 2; }
  else {
    const pod = s.instances.find((p) => p.id === instanceId);
    if (!pod) throw new Error("Instance Podu již neexistuje.");
    if (kind === "crash") { pod.state = "failed"; pod.readiness = "unavailable"; pod.failedTicks = 0; pod.processed = 0; pod.completed = 0; }
    else if (kind === "slow") pod.manualSlow = true;
    else if (kind === "restore") {
      const initializing = pod.readiness === "unavailable" && node.deployment!.readinessTicks > 0;
      pod.state = initializing ? "initializing" : "healthy"; pod.readiness = initializing ? "initializing" : "ready"; pod.readyIn = initializing ? node.deployment!.readinessTicks : 0;
      pod.failedTicks = 0; pod.manualSlow = false; delete pod.health;
    } else throw new Error("Neznámý příkaz controlleru.");
    s.events.push({ kind, message: `${pod.name}: ${kind}`, instanceId: pod.id });
  }
  // Pressure vytvoří inicializující instance hned; běžná ruční přidání zůstávají připravená.
  if (kind === "pressure" || kind === "external") return reconcileDeployment(node, s, { offered: s.externalOffered, tick: false, immediate: false, failed: false });
  Object.assign(s, controllerCounts(s));
  return s;
}

export function initializeControllers<S extends { controllers?: Record<string, Controller> }>(domain: SimDomain, state: S): S {
  state.controllers ??= {};
  const ids = new Set(domain.nodes.filter((n) => n.deployment).map((n) => n.id));
  for (const id of Object.keys(state.controllers)) if (!ids.has(id)) delete state.controllers[id];
  for (const node of domain.nodes.filter((n) => n.deployment)) if (!state.controllers[node.id]) state.controllers[node.id] = reconcileDeployment(node);
  return state;
}
