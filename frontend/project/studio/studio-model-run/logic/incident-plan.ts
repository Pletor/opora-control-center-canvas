// Plánované incidenty modelu (docs/studio.md §5: simulace nic neukládá kromě definice incidentů v modelu): incident
// z běhu se dá uložit do `modelDefinition.incidents` jako plán `{tick, kind, nodeIds}`, který engine v daném ticku
// sám provede. Plánovat jde jen crash, slow a restore od ticku 1 (validace S5); surge je přepínač zátěže běhu, ne plán.
// Model bez MODEL části ji dostane s prázdným principem a omezeními. Čistá logika bez Reactu; vrací nový model.
import { MODEL_VERSION } from "../../model/simulation/logic";
import type { IncidentKind, ModelDefinition, ModelIncident } from "../../model/simulation/logic";
import type { EditModel } from "../../studio-model/logic/model-edit";

export const PLANNABLE: readonly IncidentKind[] = ["crash", "slow", "restore"];
export const INCIDENT_LABELS: Readonly<Record<IncidentKind, string>> = { crash: "Crash", slow: "Slow ×5", restore: "Restore" };

export const isPlannable = (kind: string): kind is IncidentKind => (PLANNABLE as readonly string[]).includes(kind);

const definitionOf = (model: EditModel): ModelDefinition =>
  model.modelDefinition ?? { version: MODEL_VERSION, layer: "MODEL", principle: "", limitations: "", incidents: [] };

/** Přidá plánovaný incident; stejný tick a druh se sloučí do jednoho záznamu. Neplatný tick nebo uzel vrátí důvod. */
export function planIncident(model: EditModel, kind: IncidentKind, nodeId: string, tick: number): { model: EditModel } | { error: string } {
  if (!Number.isInteger(tick) || tick < 1) return { error: "Tick plánovaného incidentu musí být celé číslo od 1." };
  if (!isPlannable(kind)) return { error: "Plánovat jde jen crash, slow a restore." };
  if (!model.nodes.some((node) => node.id === nodeId)) return { error: "Komponenta incidentu v modelu není." };
  const definition = definitionOf(model);
  const same = definition.incidents.findIndex((incident) => incident.tick === tick && incident.kind === kind);
  const incidents: ModelIncident[] = same < 0
    ? [...definition.incidents, { tick, kind, nodeIds: [nodeId] }]
    : definition.incidents.map((incident, index) => index !== same || incident.nodeIds.includes(nodeId) ? incident : { ...incident, nodeIds: [...incident.nodeIds, nodeId] });
  incidents.sort((a, b) => a.tick - b.tick);
  return { model: { ...model, modelDefinition: { ...definition, incidents } } };
}

/** Odebere uzel z plánovaného incidentu (záznam bez uzlů zmizí). */
export function unplanIncident(model: EditModel, index: number, nodeId: string): EditModel {
  const definition = model.modelDefinition;
  if (!definition?.incidents[index]) return model;
  const incidents = definition.incidents
    .map((incident, at) => at === index ? { ...incident, nodeIds: incident.nodeIds.filter((id) => id !== nodeId) } : incident)
    .filter((incident) => incident.nodeIds.length > 0);
  return { ...model, modelDefinition: { ...definition, incidents } };
}

/** Plánované incidenty jednoho uzlu s indexem záznamu (pro výpis a odebrání). */
export function nodeIncidents(model: EditModel, nodeId: string): { index: number; incident: ModelIncident }[] {
  return (model.modelDefinition?.incidents ?? []).flatMap((incident, index) => incident.nodeIds.includes(nodeId) ? [{ index, incident }] : []);
}
