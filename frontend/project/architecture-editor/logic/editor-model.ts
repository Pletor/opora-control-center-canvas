import type { CanvasNode, EdgeCarries, ElementKind, Graph, PageSection, PageSite } from "@/shared/types/logic/types";
import { ELEMENT_LABELS } from "@/editor/canvas/create-dialog/logic/element-palette";
import { canCarry } from "@/shared/edge-carries/logic/edge-carries";
import { withCardSection } from "@/shared/card-context/logic/card-context";
import { productFingerprint } from "@/project/product-tree/logic/product-tree";
import { pageSiteForSave } from "../domain-site/logic/page-site";

const GRAPH_ID = /^[A-Za-z0-9_-]{1,80}$/;

export type ArchitectureEditorId = string;
export type EditorScopeNode = CanvasNode | null;

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

/** Prvek logiky z palety plátna 2: uzel s druhem `element` pod stránkou, název je český druh (přejmenuje se v Detailu).
 * `section` = box layoutu, do kterého prvek patří (`card.section`); bez něj je prvkem celé stránky. */
export function createEditorElementPlan(pageId: string, kind: ElementKind, section: string | null = null, name = ELEMENT_LABELS[kind]) {
  if (!GRAPH_ID.test(pageId)) throw new Error("Neplatná stránka prvku.");
  if (section !== null && !GRAPH_ID.test(section)) throw new Error("Neplatné id sekce.");
  return { nodes: [{ ref: "element", kind: "node", parent: `@${pageId}`, name, purpose: "", element: { kind }, ...(section ? { card: { section } } : {}) }] };
}

/** Prvky logiky převzatého skenu webu jedním plánem (refs `logic-<i>`, box = `card.section`; sekce už musí na stránce být). */
export function scanLogicPlan(pageId: string, logic: readonly { kind: ElementKind; name: string; purpose: string; section: string | null }[]) {
  if (!GRAPH_ID.test(pageId)) throw new Error("Neplatná stránka prvku.");
  if (logic.some((item) => item.section !== null && !GRAPH_ID.test(item.section))) throw new Error("Neplatné id sekce.");
  return { nodes: logic.map((item, index) => ({ ref: `logic-${index}`, kind: "node", parent: `@${pageId}`, name: item.name, purpose: item.purpose,
    element: { kind: item.kind }, ...(item.section ? { card: { section: item.section } } : {}) })) };
}

/**
 * Layout stránky (vrstva 1 plátna 2) jednou změnou grafu: nové `site.sections` přes `setEditorPageSite` (otisk, `pageSiteForSave`)
 * a prvkům logiky, jejichž box zmizel (odebrání, šablona), se `card.section` smaže, aby přešly na celou stránku.
 * `touched` = uzly prvků, kterým se sekce smazala (rodič u nich ověří zámek obsahu).
 */
export function setEditorPageLayout(graph: Graph, pageId: string, sections: PageSection[]): { graph: Graph; touched: string[] } {
  const page = graph.nodes.find((node) => node.id === pageId);
  if (!page || page.site?.kind !== "page") throw new Error("Layout má jen stránka.");
  const kept = new Set(sections.map((section) => section.id));
  let next = setEditorPageSite(graph, page, { ...page.site, sections });
  const touched = graph.nodes.filter((node) => node.parentId === pageId && node.kind === "node" && node.card?.section && !kept.has(node.card.section)).map((node) => node.id);
  for (const id of touched) next = setEditorNodeSection(next, id, null);
  return { graph: next, touched };
}
