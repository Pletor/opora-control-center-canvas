// Pravidla definice modelu (prototyp `model.mjs`): nová komponenta z katalogu, kontrola vazby (výstup → vstup, stejný
// datový typ, role Studia, bez duplicit), připojení a odebrání komponenty jako čisté funkce, které vrací nový model,
// a validace celé definice `opora.studio-model/1` s limity úložiště (≤ 1000 komponent, ≤ 5000 vazeb).
import { pairError, type PortEnd } from "@/shared/flow-editor/logic/connection-policy";
import { componentType } from "./catalog";
import { roleConnectionError, STUDIO_POLICY, type ConnectionPolicy } from "./connection-policy";
import { STUDIO_MODEL_SCHEMA, type Point, type Port, type PortRef, type PortType, type StudioModel, type StudioModelEdge, type StudioModelNode } from "./model-types";

export const MAX_NODES = 1000;
export const MAX_EDGES = 5000;
const newId = () => globalThis.crypto.randomUUID();

/** Výchozí konfigurace komponenty jako v prototypu (`createNode`); parametry simulace doplní etapa S5. */
export function createNode(typeId: string, position: Point = { x: 100, y: 100 }, id: string = newId()): StudioModelNode {
  const type = componentType(typeId);
  if (!type) throw new Error("Neznámý typ komponenty.");
  return { id, type: type.id, name: type.name, position: { ...position }, config: { endpoint: "", timeoutMs: 3000, region: "", zone: "", dependencyGroup: "" } };
}

type Graph = Pick<StudioModel, "nodes" | "edges">;

/** Proč vazba `from → to` neplatí; null = platí. `ignoreId` vynechá hranu sebe sama při kontrole duplicit. */
export function connectionError(model: Graph, from: PortRef | null | undefined, to: PortRef | null | undefined, ignoreId?: string, policy: ConnectionPolicy = STUDIO_POLICY): string | null {
  if (!from || !to) return "Chybí koncový bod.";
  const a = model.nodes.find((n) => n.id === from.nodeId), b = model.nodes.find((n) => n.id === to.nodeId);
  if (!a || !b) return "Komponenta neexistuje.";
  const out = componentType(a.type)?.ports.find((p) => p.id === from.portId), input = componentType(b.type)?.ports.find((p) => p.id === to.portId);
  // Společná pravidla vazby (shared/flow-editor); port se špatným směrem se bere jako neexistující a hlásí směr.
  const end = (nodeId: string, port: Port | undefined, portId: string, direction: "in" | "out"): PortEnd =>
    ({ nodeId, port: portId, direction, kind: port?.direction === (direction === "out" ? "output" : "input") ? port.type : null });
  return pairError(end(a.id, out, from.portId, "out"), end(b.id, input, to.portId, "in"), {
    self: "Komponentu nelze propojit samu se sebou.", missing: "Vazba musí vést z výstupu na vstup.",
    extra: (f) => roleConnectionError(a, b, f.kind as PortType, policy),
    exists: () => model.edges.some((e) => e.id !== ignoreId && e.from.nodeId === a.id && e.from.portId === from.portId && e.to.nodeId === b.id && e.to.portId === to.portId),
  });
}

/** Nový model s přidanou vazbou; neplatná vazba hodí chybu a model zůstane, jak byl. */
export function connect<M extends Graph>(model: M, from: PortRef, to: PortRef, policy: ConnectionPolicy = STUDIO_POLICY, id: string = newId()): { model: M; edge: StudioModelEdge } {
  const error = connectionError(model, from, to, undefined, policy);
  if (error) throw new Error(error);
  const source = model.nodes.find((n) => n.id === from.nodeId)!;
  const type = componentType(source.type)!.ports.find((p) => p.id === from.portId)!.type;
  const edge: StudioModelEdge = { id, from: { ...from }, to: { ...to }, type, label: "", enabled: true, condition: "" };
  return { model: { ...model, edges: [...model.edges, edge] }, edge };
}

/** Nový model bez komponenty a bez všech jejích vazeb. */
export function removeNode<M extends Graph>(model: M, nodeId: string): M {
  return { ...model, nodes: model.nodes.filter((n) => n.id !== nodeId), edges: model.edges.filter((e) => e.from.nodeId !== nodeId && e.to.nodeId !== nodeId) };
}

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown, max = 500): v is string => typeof v === "string" && v.length <= max;

function uniqueIds(items: unknown, label: string): void {
  if (!Array.isArray(items)) throw new Error(`${label}: očekáváno pole.`);
  const ids = new Set<string>();
  for (const item of items) {
    if (!isObject(item) || !text(item.id, 128) || !item.id || ids.has(item.id)) throw new Error(`${label}: chybné nebo duplicitní ID.`);
    ids.add(item.id);
  }
}

/** Ověří definici modelu včetně katalogu a pravidel vazeb; chyba = výjimka s českou zprávou, jinak vrací model. */
export function validateModel(model: StudioModel, policy: ConnectionPolicy = STUDIO_POLICY): StudioModel {
  if (!isObject(model) || model.schema !== STUDIO_MODEL_SCHEMA) throw new Error(`Nepodporovaná verze modelu. Požadována ${STUDIO_MODEL_SCHEMA}.`);
  if (!text(model.domainId, 128) || !model.domainId) throw new Error("Chybí doména modelu.");
  if (!Number.isInteger(model.revision) || model.revision < 0) throw new Error("Neplatná revize modelu.");
  uniqueIds(model.nodes, "nodes");
  uniqueIds(model.edges, "edges");
  if (model.nodes.length > MAX_NODES || model.edges.length > MAX_EDGES) throw new Error("Překročen limit 1000 komponent / 5000 vazeb.");
  for (const node of model.nodes) {
    if (!componentType(node.type) || !text(node.name, 200) || !node.name.trim() || !isObject(node.position) || !finite(node.position.x) || !finite(node.position.y))
      throw new Error("Neplatná komponenta.");
    if (!isObject(node.config)) throw new Error("Neplatná konfigurace komponenty.");
    if (node.binding !== undefined && (!isObject(node.binding) || !text(node.binding.nodeId, 128) || !node.binding.nodeId)) throw new Error("Neplatná vazba na kartu OPORY.");
  }
  for (const edge of model.edges) {
    const error = connectionError(model, edge.from, edge.to, edge.id, policy);
    if (error) throw new Error(error);
    const source = model.nodes.find((n) => n.id === edge.from.nodeId)!;
    if (edge.type !== componentType(source.type)!.ports.find((p) => p.id === edge.from.portId)!.type || typeof edge.enabled !== "boolean"
      || (edge.label !== undefined && !text(edge.label, 200)) || (edge.condition !== undefined && !text(edge.condition, 2000)))
      throw new Error("Neplatný typ nebo konfigurace vazby.");
  }
  return model;
}
