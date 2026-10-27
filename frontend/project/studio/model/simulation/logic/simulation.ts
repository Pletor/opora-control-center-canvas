// Engine simulace vrstvy MODEL `flow-model/1` / `flow-rules/1.18.0` (prototyp `simulation.mjs`). Vlastní výukový
// tekutinový model: jeden krok = jedna modelová sekunda, deterministický, bez náhody, nikdy měření ani spuštění služeb.
// Vstupem je model S4 (`SimulationModel`), který tenký adaptér (`model-adapter.ts`) převede na doménu enginu.
// Krok: rozvrh (`step-schedule`) → dopředný průchod (`step-forward`) → zpětný průchod (`step-backward`) → závěr (`step-summary`).
import { planCacheSettlement } from "./cache-settlement";
import { cloudProfile } from "./cloud-profiles";
import { controllerCommand, controllerFaults, initializeControllers, reconcileDeployment } from "./deployment";
import { simulationDomain, type SimulationModel } from "./model-adapter";
import { ENGINE_VERSION, MODEL_VERSION } from "./simulation-config";
import type { ModelCommandKind, SimDomain, SimEdge, SimulationState } from "./simulation-types";
import { acceptEdges, backwardPass, queueBackpressure } from "./step-backward";
import { forwardPass, initEdges } from "./step-forward";
import { schedule, type StepContext } from "./step-schedule";
import { finishStep } from "./step-summary";

export function createSimulation(): SimulationState {
  return {
    version: MODEL_VERSION, engineVersion: ENGINE_VERSION, source: "educational-model", tick: 0, nodes: {}, edges: {}, events: [], samples: [], incidents: {}, surge: 1,
    variation: false, warnings: [], definitionPending: false,
  };
}

/** Po změně definice zachová historii a stav nezměněných identit; osiřelé a typově změněné uzly a změněné vazby zahodí. */
export function rebaseSimulation(model: SimulationModel, previous: SimulationState, oldModel: SimulationModel): SimulationState {
  const domain = simulationDomain(model), oldDefinition = simulationDomain(oldModel);
  const state = structuredClone(previous), oldNodes = new Map(oldDefinition.nodes.map((n) => [n.id, n.type])), nodeIds = new Set(domain.nodes.filter((n) => oldNodes.get(n.id) === n.type).map((n) => n.id));
  state.nodes = Object.fromEntries(Object.entries(state.nodes).filter(([id]) => nodeIds.has(id)));
  state.incidents = Object.fromEntries(Object.entries(state.incidents).filter(([id]) => nodeIds.has(id)));
  const signature = (e: SimEdge) => JSON.stringify([e.from, e.to, e.type, e.enabled, e.condition]), oldEdges = new Map(oldDefinition.edges.map((e) => [e.id, signature(e)]));
  const edgeIds = new Set(domain.edges.filter((e) => oldEdges.get(e.id) === signature(e)).map((e) => e.id));
  state.edges = Object.fromEntries(Object.entries(state.edges).filter(([id]) => edgeIds.has(id)));
  state.definitionPending = state.tick > 0;
  initializeControllers(domain, state);
  for (const node of domain.nodes.filter((n) => n.deployment)) state.controllers![node.id] = reconcileDeployment(node, state.controllers![node.id]);
  return state;
}

function command(state: SimulationState, domain: SimDomain, kind: ModelCommandKind, nodeIds: readonly string[]): void {
  const recoverySteps = (nodeId: string) => (["connection-pool", "object-store"].includes(cloudProfile(domain.nodes.find((n) => n.id === nodeId)?.type) as string) ? 1 : 2);
  if (kind === "surge") { state.surge = state.surge === 1 ? 5 : 1; return; }
  if (kind === "variation") { state.variation = !state.variation; return; }
  if (kind === "restore-all") {
    const ids = new Set([...Object.keys(state.incidents), ...Object.values(state.nodes).filter((row) => row.autoFailed).map((row) => row.nodeId)]);
    for (const key of ids) state.incidents[key] = { kind: "recovering", remaining: recoverySteps(key) };
    for (const fault of controllerFaults(state)) {
      const node = domain.nodes.find((n) => n.id === fault.parentId)!;
      state.controllers![node.id] = controllerCommand(node, state.controllers![node.id], "restore", fault.instanceId);
    }
    return;
  }
  for (const nodeId of nodeIds) {
    if (!domain.nodes.some((n) => n.id === nodeId)) throw new Error("Komponenta incidentu neexistuje.");
    state.incidents[nodeId] = kind === "restore" ? { kind: "recovering", remaining: recoverySteps(nodeId) } : { kind, remaining: 0 };
  }
}

/** Příkaz běhu nad stavem (mění `state` na místě): surge 5×, slow, crash, restore, variation, restore-all. */
export function modelCommand(state: SimulationState, model: SimulationModel, kind: ModelCommandKind, nodeIds: readonly string[] = []): void {
  command(state, simulationDomain(model), kind, nodeIds);
}

/** Jeden krok modelu. `preview` přepočte aktuální graf bez posunu času, backlogu a čítačů (náhled po změně definice). */
export function stepSimulation(model: SimulationModel, previous: SimulationState = createSimulation(), { preview = false }: { preview?: boolean } = {}): SimulationState {
  const domain = simulationDomain(model), s = initializeControllers(domain, structuredClone(previous));
  if (!preview) s.tick++;
  s.nodes = {}; s.edges = {}; s.warnings = []; s.definitionPending = false; s.preview = preview;
  if (!preview) for (const event of domain.modelDefinition?.incidents || []) if (event.tick === s.tick) command(s, domain, event.kind, event.nodeIds);
  const graph = schedule(domain), settlement = planCacheSettlement(domain, graph);
  s.warnings.push(...settlement.warnings);
  const ctx: StepContext = {
    domain, previous, s, preview, order: settlement.order, edges: graph.edges, delayed: graph.delayed, plans: settlement.plans,
    byId: new Map(domain.nodes.map((n) => [n.id, n])), incoming: new Map(domain.nodes.map((n) => [n.id, []])),
    emitEvent: (nodeId, kind, message) => { if (!preview) s.events.push({ id: `model-${s.tick}-${s.events.length}`, tick: s.tick, at: `model tick ${s.tick}`, nodeId, kind, message, source: "educational-model" }); },
  };
  initEdges(ctx);
  forwardPass(ctx);
  acceptEdges(ctx);
  queueBackpressure(ctx);
  // Zpětný průchod vrací dokončení a zpětný tlak jen po synchronních závislostech.
  backwardPass(ctx);
  finishStep(ctx);
  return s;
}

export function previewSimulation(model: SimulationModel, state: SimulationState = createSimulation()): SimulationState {
  return stepSimulation(model, state, { preview: true });
}
