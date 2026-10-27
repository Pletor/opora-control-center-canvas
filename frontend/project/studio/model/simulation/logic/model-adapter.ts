// Tenký adaptér modelu S4 (`opora.studio-model/1`) na doménu enginu prototypu. Model S4 nemá `contracts`, `lifecycle`,
// `implementation` ani `node.deployment`; engine je nepotřebuje kromě Deploymentu. Proto:
// - parametry simulace leží v `config.model` (jako v prototypu), ruční přepisy výstupů v `config.outputOverrides`;
// - definice šablony Podů leží v `config.deployment` a čte se jen u typu `kubernetes-deployment`;
// - řízený Pod (`type: "pod"` s `parentId`) je v enginu instance controlleru, ne uzel; do výpočtu nevstupuje
//   (pravidla vazeb S4 na něj stejně nedovolí vazbu);
// - plán incidentů a údaje scénáře nese volitelné `modelDefinition` vedle uzlů a hran.
// Adaptér nic nekopíruje: `config` zůstává stejný objekt, takže změna parametru v modelu se projeví dalším krokem.
import { createNode } from "../../logic/model-rules";
import type { Point, StudioModel, StudioModelNode } from "../../logic/model-types";
import { deploymentDefinition } from "./deployment-definition";
import type { DeploymentDefinition, ModelDefinition, SimDomain, SimNode } from "./simulation-types";

/** Vstup simulace: uzly a hrany modelu S4, volitelně s definicí MODEL části (plán incidentů, scénář). */
export type SimulationModel = Pick<StudioModel, "nodes" | "edges"> & { modelDefinition?: ModelDefinition };

const isObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);

/** Řízený Pod uvnitř Deploymentu: v modelu jen kvůli zobrazení, v enginu ho zastupuje controller. */
export const isManagedPod = (node: StudioModelNode): boolean => node.type === "pod" && Boolean(node.parentId);

/** Definice šablony Podů uzlu; jen `kubernetes-deployment` s objektem v `config.deployment`. */
export function deploymentOf(node: StudioModelNode): DeploymentDefinition | undefined {
  return node.type === "kubernetes-deployment" && isObject(node.config.deployment) ? node.config.deployment as DeploymentDefinition : undefined;
}

export function simulationDomain(model: SimulationModel): SimDomain {
  const nodes: SimNode[] = model.nodes.filter((n) => !isManagedPod(n)).map((n) => ({ ...n, deployment: deploymentOf(n) }));
  const ids = new Set(nodes.map((n) => n.id));
  return { nodes, edges: model.edges.filter((e) => ids.has(e.from.nodeId) && ids.has(e.to.nodeId)), modelDefinition: model.modelDefinition };
}

/** Výchozí konfigurace simulace nové komponenty jako v prototypu (`createNode`): Deployment dostane šablonu Podů
 *  a automatické selhání po 3 krocích přetížení, Service podíl telemetrie 0,01. Vrací nový uzel. */
export function withSimulationDefaults(node: StudioModelNode, templateId = `${node.id}:pods`): StudioModelNode {
  if (node.type === "kubernetes-deployment") return { ...node, config: { ...node.config, model: { crashAfterTicks: 3 }, deployment: deploymentDefinition(templateId) } };
  if (node.type === "service") return { ...node, config: { ...node.config, model: { telemetryRate: .01 } } };
  return node;
}

/** Nová komponenta katalogu s výchozí konfigurací simulace (S4 `createNode` + `withSimulationDefaults`). */
export function createSimulationNode(typeId: string, position: Point = { x: 100, y: 100 }, id?: string): StudioModelNode {
  return withSimulationDefaults(createNode(typeId, position, id));
}
