import type { CanvasNode, EdgeCarries, Graph, PageSite } from "@/shared/types/logic/types";
import { canCarry } from "@/shared/edge-carries/logic/edge-carries";
import { withCardSection } from "@/shared/card-context/logic/card-context";
import { moveWithMembers, resizeArea } from "@/editor/canvas/area/logic/area-model";
import { productFingerprint } from "@/project/product-tree/logic/product-tree";
import { pageSiteForSave } from "../domain-map/logic/page-site";

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

/** Domovská oblast vyrostla za puštěnou kartou (`area-growth.ts`): nová poloha i rozměr (120..20000), členové stojí. */
export function growEditorArea(graph: Graph, frame: { id: string; x: number; y: number; w: number; h: number }): Graph {
  if (![frame.x, frame.y].every((value) => Number.isFinite(value) && Math.abs(value) <= 1_000_000)) throw new Error("Neplatná poloha oblasti.");
  const area = graph.nodes.find((node) => node.id === frame.id);
  if (!area || area.kind !== "area") throw new Error("Oblast již neexistuje.");
  const grown = { ...resizeEditorNode(graph, frame.id, frame.w, frame.h).nodes.find((node) => node.id === frame.id)!, x: frame.x, y: frame.y };
  return { ...graph, nodes: graph.nodes.map((node) => node.id === frame.id ? grown : node) };
}

/**
 * Pravidlo vazby na mapě (tah z portu i nabídka vazby z portu, `port-menu/`): proč `source → target` nejde,
 * nebo `null`, když jde. Bez sebe sama, bez komentářů, oblast jen s oblastí (`flow`) a bez duplicitní vazby.
 */
export function connectionProblem(graph: Graph, source: string, target: string): string | null {
  if (source === target) return "Prvek nelze propojit se sebou.";
  const from = graph.nodes.find((node) => node.id === source);
  const to = graph.nodes.find((node) => node.id === target);
  if (!from || !to || from.kind === "comment" || to.kind === "comment") return "Vazba vyžaduje dva prvky bez komentářů.";
  if ((from.kind === "area") !== (to.kind === "area")) return "Oblast lze propojit jen s jinou oblastí.";
  const port = from.kind === "area" ? "flow" : "next";
  if (graph.edges.some((edge) => edge.source === source && edge.target === target && (edge.port ?? "next") === port)) return "Tato vazba již existuje.";
  if (port === "next" && nextReaches(graph, target, source)) return "Vazba by uzavřela cyklus karet; server ji odmítne.";
  return null;
}

/** Vede z `from` cesta po vazbách `next` mezi kartami do `to`? Totéž pravidlo hlídá backend `card_dag.py`. */
function nextReaches(graph: Graph, from: string, to: string): boolean {
  const cards = new Set(graph.nodes.filter((node) => node.kind === "node" || node.kind === "sector").map((node) => node.id));
  const seen = new Set([from]); const queue = [from];
  while (queue.length) {
    const current = queue.shift()!;
    if (current === to) return true;
    for (const edge of graph.edges) {
      if (edge.source !== current || (edge.port ?? "next") !== "next" || !cards.has(edge.source) || !cards.has(edge.target) || seen.has(edge.target)) continue;
      seen.add(edge.target); queue.push(edge.target);
    }
  }
  return false;
}

/** Nová vazba; `carries` (druh toku z nabídky vazby) dostane jen vazba `next`, tah z portu ho nenese. */
export function connectEditorNodes(graph: Graph, source: string, target: string, id: string, carries?: EdgeCarries | null): Graph {
  if (!GRAPH_ID.test(id) || graph.edges.some((edge) => edge.id === id)) throw new Error("Neplatná nebo již použitá identita vazby.");
  const problem = connectionProblem(graph, source, target);
  if (problem) throw new Error(problem);
  const port = graph.nodes.find((node) => node.id === source)!.kind === "area" ? "flow" : "next";
  return { ...graph, edges: [...graph.edges, { id, source, target, port, ...(carries && port === "next" ? { carries } : {}) }] };
}

/** Člověk určí, co po vazbě teče; `null` = neurčeno (klíč zmizí, nic se nedoplňuje). Jen vazba `next`. */
export function setEditorEdgeCarries(graph: Graph, edgeId: string, carries: EdgeCarries | null): Graph {
  const edge = graph.edges.find((item) => item.id === edgeId);
  if (!edge) throw new Error("Vazba již neexistuje.");
  if (!canCarry(edge)) throw new Error("Druh toku smí mít jen vazba next.");
  if ((edge.carries ?? null) === carries) return graph;
  const { carries: _previous, ...rest } = edge;
  const next = carries ? { ...rest, carries } : rest;
  return { ...graph, edges: graph.edges.map((item) => item.id === edgeId ? next : item) };
}

/** Vazby, které člověk v editoru kreslí (`next` mezi kartami, `flow` mezi oblastmi), smí také odebrat; jiné porty ne. */
export function canRemoveEditorEdge(edge: { port?: string | null }): boolean {
  const port = edge.port ?? "next";
  return port === "next" || port === "flow";
}

/**
 * Člověk určí, kterou sekci stránky komponenta realizuje (`card.section`, docs/architektura-pro-agenty.md §3.3);
 * `null` = neurčeno (klíč zmizí, nic se nedoplňuje). Ostatní pole karty zůstanou. Existenci sekce tu nehlídáme:
 * výběr nabízí jen sekce nejbližší stránky a díru po smazané sekci ohlásí kontrola mapy (`section.unknown`).
 */
export function setEditorNodeSection(graph: Graph, nodeId: string, section: string | null): Graph {
  const node = graph.nodes.find((item) => item.id === nodeId);
  if (!node) throw new Error("Prvek již neexistuje.");
  if (node.kind !== "node") throw new Error("Sekci stránky realizuje jen uzel.");
  if (section !== null && !GRAPH_ID.test(section)) throw new Error("Neplatné id sekce.");
  if ((node.card?.section ?? null) === section) return graph;
  return { ...graph, nodes: graph.nodes.map((item) => item.id === nodeId ? withCardSection(item, section) : item) };
}

/**
 * Člověk uloží záměr a sekce stránky ze záložky Stránka v Detailu prvku (cíl, působení, popisek v menu, sekce
 * s `moves`; docs/architektura-pro-agenty.md §3.1). `original` je stránka, ze které koncept vznikl: změnil-li ji
 * mezitím někdo jiný (otisk `productFingerprint`), uložení se odmítne a koncept zůstane. Cesta stránky se tu
 * nemění; text se ořízne a prázdné pole vynechá (`pageSiteForSave`). Beze změny vrací týž graf.
 */
export function setEditorPageSite(graph: Graph, original: CanvasNode, site: PageSite): Graph {
  const node = graph.nodes.find((item) => item.id === original.id);
  if (!node) throw new Error("Stránka již neexistuje.");
  if (node.site?.kind !== "page") throw new Error("Záměr a sekce má jen stránka.");
  if (productFingerprint(node) !== productFingerprint(original)) throw new Error("Stránka se mezitím změnila. Zrušte koncept a otevřete aktuální hodnoty.");
  const next = pageSiteForSave({ ...site, kind: "page", path: node.site.path });
  if (JSON.stringify(next) === JSON.stringify(node.site)) return graph;
  return { ...graph, nodes: graph.nodes.map((item) => item.id === node.id ? { ...item, site: next } : item) };
}

export function createEditorAreaPlan(parentId: string | null, name = "Nová oblast"): EditorAreaPlan {
  if (parentId !== null && !GRAPH_ID.test(parentId)) throw new Error("Neplatný rodič oblasti.");
  const title = name.trim();
  if (!title || title.length > 120) throw new Error("Název oblasti musí mít 1–120 znaků.");
  return { nodes: [{ ref: "area", kind: "area", parent: parentId === null ? null : `@${parentId}`, name: title, purpose: "", size: { w: 720, h: 480 } }] };
}
