import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { moveWithMembers, resizeArea } from "@/editor/canvas/area/logic/area-model";

const GRAPH_ID = /^[A-Za-z0-9_-]{1,80}$/;

export type ArchitectureEditorId = string;
export type EditorScopeNode = CanvasNode | null;
export type EditorAreaPlan = { nodes: [{ ref: "area"; kind: "area"; parent: string | null; name: string; purpose: ""; size: { w: 720; h: 480 } }] };

/** Identity belongs to the persisted project/workspace, independent of UI state. */
export function architectureEditorId(project: string, workspace: string, domainId?: string): ArchitectureEditorId {
  if (!project || !workspace) throw new Error("Editor vyžaduje projekt a pracovní prostor.");
  if (domainId !== undefined && !domainId) throw new Error("Editor domény vyžaduje její ID.");
  return `opora:architecture:v1:${encodeURIComponent(project)}:${encodeURIComponent(workspace)}${domainId === undefined ? "" : `:domain:${encodeURIComponent(domainId)}`}`;
}

export function validateEditorRoute(value: string | null, project: string, workspace: string, domainId?: string): ArchitectureEditorId {
  const expected = architectureEditorId(project, workspace, domainId);
  if (value !== null && value !== expected) throw new Error("Identita editoru neodpovídá projektu a pracovnímu prostoru.");
  return expected;
}

export function editorScopeNode(graph: Graph, pageId: string | null): EditorScopeNode {
  if (pageId === null) return null;
  const node = graph.nodes.find((item) => item.id === pageId);
  if (!node || (node.kind !== "node" && node.kind !== "sector")) throw new Error("Tato část projektu není dostupným rozsahem editoru.");
  return node;
}

export function isEditorScopeClosed(graph: Graph, nodeId: string | null, closedIds: ReadonlySet<string>): boolean {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const seen = new Set<string>();
  let cursor = nodeId;
  while (cursor !== null) {
    if (seen.has(cursor)) throw new Error("Strom projektu obsahuje cyklus.");
    seen.add(cursor);
    const node = byId.get(cursor);
    if (!node) throw new Error("Část projektu již neexistuje.");
    if (closedIds.has(cursor)) return true;
    cursor = node.parentId;
  }
  return false;
}

/** Patch the full graph: unrelated branches and optional metadata stay intact. */
export function moveEditorNode(graph: Graph, id: string, x: number, y: number): Graph {
  if (![x, y].every((value) => Number.isFinite(value) && Math.abs(value) <= 1_000_000)) throw new Error("Neplatná poloha prvku.");
  const moved = graph.nodes.find((node) => node.id === id);
  if (!moved) throw new Error("Prvek již neexistuje.");
  const nodes = moved.kind === "area" ? moveWithMembers(graph.nodes, id, x - moved.x, y - moved.y)
    : graph.nodes.map((node) => node.id === id ? { ...node, x, y } : node);
  if (nodes.some((node) => ![node.x, node.y].every((value) => Number.isFinite(value) && Math.abs(value) <= 1_000_000))) throw new Error("Prvek by se přesunul mimo povolené souřadnice.");
  return { ...graph, nodes };
}

/** Tahadlo rámečku oblasti: nový rozměr ohraničený na 120..20000 (`resizeArea`), ostatní uzly beze změny. */
export function resizeEditorNode(graph: Graph, id: string, w: number, h: number): Graph {
  if (![w, h].every((value) => Number.isFinite(value) && value > 0)) throw new Error("Neplatný rozměr oblasti.");
  const area = graph.nodes.find((node) => node.id === id);
  if (!area) throw new Error("Prvek již neexistuje.");
  if (area.kind !== "area") throw new Error("Velikost lze měnit jen oblasti.");
  const resized = resizeArea(area, w, h);
  if (resized.size!.w === area.size?.w && resized.size!.h === area.size?.h) return graph;
  return { ...graph, nodes: graph.nodes.map((node) => node.id === id ? resized : node) };
}

export function connectEditorNodes(graph: Graph, source: string, target: string, id: string): Graph {
  if (!GRAPH_ID.test(id) || graph.edges.some((edge) => edge.id === id)) throw new Error("Neplatná nebo již použitá identita vazby.");
  if (source === target) throw new Error("Prvek nelze propojit se sebou.");
  const from = graph.nodes.find((node) => node.id === source);
  const to = graph.nodes.find((node) => node.id === target);
  if (!from || !to || from.kind === "comment" || to.kind === "comment") throw new Error("Vazba vyžaduje dva prvky bez komentářů.");
  if ((from.kind === "area") !== (to.kind === "area")) throw new Error("Oblast lze propojit jen s jinou oblastí.");
  const port = from.kind === "area" ? "flow" : "next";
  if (graph.edges.some((edge) => edge.source === source && edge.target === target && (edge.port ?? "next") === port)) throw new Error("Tato vazba již existuje.");
  return { ...graph, edges: [...graph.edges, { id, source, target, port }] };
}

export function createEditorAreaPlan(parentId: string | null, name = "Nová oblast"): EditorAreaPlan {
  if (parentId !== null && !GRAPH_ID.test(parentId)) throw new Error("Neplatný rodič oblasti.");
  const title = name.trim();
  if (!title || title.length > 120) throw new Error("Název oblasti musí mít 1–120 znaků.");
  return { nodes: [{ ref: "area", kind: "area", parent: parentId === null ? null : `@${parentId}`, name: title, purpose: "", size: { w: 720, h: 480 } }] };
}
