import type { CanvasNode, Graph, GraphEdge } from "@/shared/types/logic/types";
import type { GraphContext } from "./graph-proposals";

export const editFields = ["name", "purpose", "parentId", "sourceRef", "x", "y", "size"] as const;
export type EditField = typeof editFields[number];
export const editLabels: Record<EditField, string> = { name: "Název", purpose: "Účel", parentId: "Rodič", sourceRef: "Zdroj", x: "Souřadnice X", y: "Souřadnice Y", size: "Rozměry oblasti" };
export type NodeEdit = { id: string; remove: boolean; selected: EditField[]; name: string; purpose: string; parentId: string;
  sourceOrigin: "" | "existing" | "planned"; sourcePath: string; sourceKind: "file" | "directory"; x: string; y: string; width: string; height: string; clearSize: boolean };
export type EdgeEdit = { id: string; remove: boolean; source: string; target: string };
export type EditDraft = { nodes: NodeEdit[]; edges: EdgeEdit[]; adoptArchitectureContext?: boolean };
type Change<T> = { id: string; operation: "update" | "remove" | "add"; fields: string[];
  acceptedBefore: T | null; workingBefore: T | null; proposedAccepted: T | null; proposedWorking: T | null };
export type GraphChanges = { nodes: Change<CanvasNode>[]; edges: Change<GraphEdge>[];
  architectureContext?: { acceptedBefore: Graph; workingBefore: Graph; proposedAccepted: Graph; proposedWorking: Graph } | null;
  areaMembership: { id: string; acceptedBefore: string | null; workingBefore: string | null; proposedAccepted: string | null; proposedWorking: string | null }[] };
export function editableNodes(context: GraphContext) {
  return [...new Map([...(context.acceptedGraph?.nodes ?? []), ...(context.workingGraph?.nodes ?? [])].map(node => [node.id, node])).values()];
}
export function editableEdges(context: GraphContext) {
  return [...new Map([...(context.acceptedGraph?.edges ?? []), ...(context.workingGraph?.edges ?? [])].map(edge => [edge.id, edge])).values()];
}
export function nodeEdit(node: CanvasNode): NodeEdit {
  return { id: node.id, remove: false, selected: [], name: node.name, purpose: node.purpose ?? "", parentId: node.parentId ?? "",
    sourceOrigin: node.sourceRef?.origin ?? "", sourcePath: node.sourceRef?.path ?? "", sourceKind: node.sourceRef?.kind ?? "file",
    x: String(node.x), y: String(node.y), width: String(node.size?.w ?? 1200), height: String(node.size?.h ?? 800), clearSize: false };
}
export function graphEditPayload(project: string, workspace: string, subject: string, context: GraphContext, draft: EditDraft) {
  if (context.readOnly || !context.graphManifestId || !context.acceptedGraph) throw new Error("Nejprve výslovně převezměte výchozí graf.");
  if (!subject.trim() || !draft.nodes.length && !draft.edges.length && !draft.adoptArchitectureContext) throw new Error("Vyplňte důvod a vyberte změny nebo odstranění.");
  if (draft.adoptArchitectureContext && !context.architectureContext?.differs) throw new Error("Kontext architektury se neliší; není co převzít.");
  const ids = new Set(editableNodes(context).map(node => node.id));
  const edgeIds = new Set(editableEdges(context).filter(edge => !edge.port || edge.port === "next").map(edge => edge.id));
  if (new Set(draft.nodes.map(node => node.id)).size !== draft.nodes.length || new Set(draft.edges.map(edge => edge.id)).size !== draft.edges.length)
    throw new Error("Stejný prvek nelze změnit vícekrát.");
  if (draft.nodes.some(node => !ids.has(node.id)) || draft.edges.some(edge => !edgeIds.has(edge.id))) throw new Error("Vybraný prvek již není v načteném kontextu.");
  const updateNodes = draft.nodes.filter(node => !node.remove).map(node => {
    if (!context.workingGraph?.nodes.some(current => current.id === node.id) || !node.selected.length) throw new Error("Pro úpravu vyberte existující pracovní prvek a alespoň jedno pole.");
    const fields: Record<string, unknown> = {};
    for (const field of editFields.filter(field => node.selected.includes(field))) {
      if (field === "name") { if (!node.name.trim()) throw new Error("Název nesmí být prázdný."); fields.name = node.name.trim(); }
      else if (field === "purpose") fields.purpose = node.purpose;
      else if (field === "parentId") {
        if (node.parentId && (!ids.has(node.parentId) || node.parentId === node.id)) throw new Error("Zkontrolujte rodiče prvku.");
        fields.parentId = node.parentId || null;
      } else if (field === "x" || field === "y") {
        if (!node[field].trim() || !Number.isFinite(Number(node[field]))) throw new Error("Souřadnice musí být konečné číslo.");
        fields[field] = Number(node[field]);
      } else if (field === "sourceRef") {
        if (node.sourceOrigin && !node.sourcePath.trim()) throw new Error("Vyplňte cestu ke zdroji.");
        fields.sourceRef = node.sourceOrigin ? { origin: node.sourceOrigin, kind: node.sourceKind, path: node.sourcePath.trim() } : null;
      } else if (field === "size") {
        if (!node.clearSize && [node.width, node.height].some(value => !/^\d+$/.test(value) || Number(value) < 120 || Number(value) > 20000)) throw new Error("Rozměry oblasti musí být celá čísla od 120 do 20000.");
        fields.size = node.clearSize ? null : { w: Number(node.width), h: Number(node.height) };
      }
    }
    return { id: node.id, fields };
  });
  const updateEdges = draft.edges.filter(edge => !edge.remove).map(edge => {
    if (!context.workingGraph?.edges.some(current => current.id === edge.id) || !ids.has(edge.source) || !ids.has(edge.target) || edge.source === edge.target)
      throw new Error("Zkontrolujte oba konce upravované vazby.");
    return { id: edge.id, source: edge.source, target: edge.target, port: "next" as const };
  });
  return { project, workspace, subject: subject.trim(), parentRevision: context.acceptedHead, expectedGraphDigest: context.graphDigest,
    plan: { updateNodes, removeNodes: draft.nodes.filter(node => node.remove).map(node => node.id), updateEdges, removeEdges: draft.edges.filter(edge => edge.remove).map(edge => edge.id),
      ...(draft.adoptArchitectureContext ? { adoptArchitectureContext: true as const } : {}) } };
}
