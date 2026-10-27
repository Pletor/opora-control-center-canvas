// Validace simulační části modelu (část prototypového `validateDomain`, která patří simulaci): `config.model` podle typu,
// ruční přepisy výstupů, definice Deploymentu jen u controlleru a jedinečná šablona Podů, plán incidentů. Tvar modelu,
// katalog a vazby ověřuje S4 `validateModel` (zavolá se jako první, s pravidly vazeb scénáře).
import { componentType } from "../../logic/catalog";
import { STUDIO_POLICY, type ConnectionPolicy } from "../../logic/connection-policy";
import { validateModel } from "../../logic/model-rules";
import type { StudioModel } from "../../logic/model-types";
import { validateDeployment } from "./deployment-definition";
import { MODEL_VERSION, validateModelConfig } from "./simulation-config";
import type { ModelDefinition } from "./simulation-types";

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown, max = 500): v is string => typeof v === "string" && v.length <= max;

export function validateSimulationModel<M extends StudioModel & { modelDefinition?: ModelDefinition }>(model: M): M {
  validateModel(model, (model.modelDefinition?.connectionPolicy as ConnectionPolicy | undefined) ?? STUDIO_POLICY);
  for (const node of model.nodes) {
    validateModelConfig(node.config.model, node.type);
    const overrides = node.config.outputOverrides;
    if (overrides !== undefined && (!isObject(overrides) || Object.entries(overrides).some(([key, value]) =>
      !componentType(node.type)!.ports.some((p) => p.id === key && p.direction === "output") || !finite(value) || value < 0 || value > 1e9)))
      throw new Error("Invalid component output override");
    if (node.config.deployment !== undefined) {
      if (node.type !== "kubernetes-deployment") throw new Error("Deployment definice patří pouze controlleru.");
      validateDeployment(node.config.deployment);
    }
  }
  const templateIds = new Set(model.nodes.map((n) => n.id));
  for (const node of model.nodes) {
    const templateId = (node.config.deployment as { templateId?: string } | undefined)?.templateId;
    if (templateId === undefined) continue;
    if (templateIds.has(templateId)) throw new Error("Duplicitní identita Pod šablony.");
    templateIds.add(templateId);
  }
  const definition = model.modelDefinition;
  if (definition !== undefined) {
    if (!isObject(definition) || definition.version !== MODEL_VERSION || definition.layer !== "MODEL" || !Array.isArray(definition.incidents)
      || !text(definition.principle, 10000) || !text(definition.limitations, 10000)) throw new Error("Neplatná definice modelu.");
    for (const event of definition.incidents)
      if (!Number.isInteger(event.tick) || event.tick < 1 || !["crash", "slow", "restore"].includes(event.kind) || !Array.isArray(event.nodeIds)
        || event.nodeIds.some((id) => !model.nodes.some((n) => n.id === id))) throw new Error("Neplatný plán modelového incidentu.");
  }
  return model;
}
