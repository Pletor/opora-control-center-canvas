// Editace technického modelu domény (vrstva MODEL, docs/studio.md §4) jako čisté funkce: každá vrací nový model a
// starý nechá, jak byl, takže je z nich historie zpět / znovu. Nová komponenta dostane výchozí konfiguraci simulace
// (`createSimulationNode`), vazba se kontroluje pravidly modelu (`connectionError` s politikou definice modelu).
import { componentType } from "../../model/logic/catalog";
import { STUDIO_POLICY, type ConnectionPolicy } from "../../model/logic/connection-policy";
import { connect, connectionError, removeNode } from "../../model/logic/model-rules";
import type { Point, PortRef, StudioModel, StudioModelEdge, StudioModelNode } from "../../model/logic/model-types";
import { createSimulationNode } from "../../model/simulation/logic/model-adapter";
import type { ModelDefinition } from "../../model/simulation/logic/simulation-types";

/** Model, jak ho edituje Studio: S4 definice a volitelná MODEL část S5 (plán incidentů, politika vazeb scénáře). */
export type EditModel = StudioModel & { modelDefinition?: ModelDefinition };
export type Selection = { kind: "node" | "edge"; id: string } | null;
export type EdgePatch = Partial<Pick<StudioModelEdge, "enabled" | "label" | "condition">>;

export const policyOf = (model: EditModel): ConnectionPolicy => (model.modelDefinition?.connectionPolicy as ConnectionPolicy | undefined) ?? STUDIO_POLICY;

const SLOT_X = 300, SLOT_Y = 280, COLUMNS = 4, ORIGIN = 80;

/** Volné místo pro komponentu přidanou klikem: první pozice mřížky 4 sloupců, u které ještě žádná karta neleží. */
export function placeNew(model: EditModel): Point {
  for (let index = 0; ; index++) {
    const slot = { x: ORIGIN + (index % COLUMNS) * SLOT_X, y: ORIGIN + Math.floor(index / COLUMNS) * SLOT_Y };
    if (!model.nodes.some((node) => Math.abs(node.position.x - slot.x) < SLOT_X / 2 && Math.abs(node.position.y - slot.y) < SLOT_Y / 2)) return slot;
  }
}

/** Název, který v modelu ještě není („Service“, „Service 2“…), aby se karty daly rozlišit v inspektoru i ve výběru. */
export function uniqueName(model: EditModel, base: string): string {
  const taken = new Set(model.nodes.map((node) => node.name));
  if (!taken.has(base)) return base;
  let index = 2;
  while (taken.has(`${base} ${index}`)) index++;
  return `${base} ${index}`;
}

export function addNode(model: EditModel, typeId: string, position: Point = placeNew(model), id?: string): { model: EditModel; node: StudioModelNode } {
  const created = createSimulationNode(typeId, { x: Math.round(position.x), y: Math.round(position.y) }, id);
  const node = { ...created, name: uniqueName(model, created.name) };
  return { model: { ...model, nodes: [...model.nodes, node] }, node };
}

const mapNode = (model: EditModel, id: string, change: (node: StudioModelNode) => StudioModelNode): EditModel =>
  ({ ...model, nodes: model.nodes.map((node) => node.id === id ? change(node) : node) });

export function moveNode(model: EditModel, id: string, position: Point): EditModel {
  return mapNode(model, id, (node) => ({ ...node, position: { x: Math.round(position.x), y: Math.round(position.y) } }));
}

/** Vazba z výstupu na vstup; nepovolená vrátí krátký důvod a model se nezmění. */
export function connectPorts(model: EditModel, from: PortRef, to: PortRef, id?: string): { model: EditModel; edgeId: string } | { error: string } {
  const error = connectionError(model, from, to, undefined, policyOf(model));
  if (error) return { error };
  const result = connect(model, from, to, policyOf(model), id);
  return { model: result.model, edgeId: result.edge.id };
}

/** Smaže vybranou komponentu (i s jejími vazbami a výskyty v plánu incidentů) nebo vybranou vazbu. */
export function removeSelected(model: EditModel, selection: Selection): EditModel {
  if (!selection) return model;
  if (selection.kind === "edge") return { ...model, edges: model.edges.filter((edge) => edge.id !== selection.id) };
  const next = removeNode(model, selection.id);
  const definition = model.modelDefinition;
  if (!definition) return next;
  const incidents = definition.incidents.map((incident) => ({ ...incident, nodeIds: incident.nodeIds.filter((id) => id !== selection.id) }))
    .filter((incident) => incident.nodeIds.length > 0);
  return { ...next, modelDefinition: { ...definition, incidents } };
}

export function renameNode(model: EditModel, id: string, name: string): EditModel {
  return mapNode(model, id, (node) => ({ ...node, name: name.slice(0, 200) }));
}

/** Váže technickou kartu na kartu OPORY; null vazbu zruší. */
export function setBinding(model: EditModel, id: string, cardId: string | null): EditModel {
  return mapNode(model, id, ({ binding: _old, ...node }) => cardId ? { ...node, binding: { nodeId: cardId } } : node);
}

/** Parametr simulace v `config.model`; undefined = vrátit výchozí hodnotu (klíč zmizí, prázdný `model` také). */
export function setParameter(model: EditModel, id: string, key: string, value: number | string | undefined): EditModel {
  return mapNode(model, id, (node) => {
    const current = { ...(node.config.model as Record<string, unknown> | undefined ?? {}) };
    if (value === undefined) delete current[key]; else current[key] = value;
    const { model: _old, ...config } = node.config;
    return { ...node, config: Object.keys(current).length ? { ...config, model: current } : config };
  });
}

export function updateEdge(model: EditModel, id: string, patch: EdgePatch): EditModel {
  return { ...model, edges: model.edges.map((edge) => edge.id === id ? { ...edge, ...patch } : edge) };
}

/** Směr portu komponenty v modelu; neznámý port = null. */
export function portDirection(model: EditModel, ref: PortRef): "input" | "output" | null {
  const node = model.nodes.find((item) => item.id === ref.nodeId);
  return (node && componentType(node.type)?.ports.find((port) => port.id === ref.portId)?.direction) ?? null;
}
