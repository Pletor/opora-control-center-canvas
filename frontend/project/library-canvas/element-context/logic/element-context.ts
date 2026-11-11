// Kontext prvku logiky pro plátno toku v projektu (docs/navrhy/2026-11-10-platno-2.md, verze 4): plátno
// `opora:project-flow:<nodeId>`, jehož uzel je prvek plátna 2 (`element`), ukáže v hlavičce druh a název prvku,
// stránku › box a návrat na plán stránky. Bez Reactu, test vedle.
import type { Graph } from "@/shared/types/logic/types";
import { logicLook } from "@/project/architecture-editor/page-editor/element-palette/logic/logic-groups";
import { domainForNode } from "@/project/architecture-editor/logic/domain-model";

export type ElementContext = { nodeId: string; kind: string; name: string; pageId: string; page: string; box: string | null; domainId: string };

/** Prvek, stránka (rodič prvku), box (`card.section` v sekcích stránky) a doména; jiný uzel nebo neúplný strom = null. */
export function elementContext(graph: Graph, nodeId: string): ElementContext | null {
  const node = graph.nodes.find((item) => item.id === nodeId);
  const page = node?.element && graph.nodes.find((item) => item.id === node.parentId);
  if (!node?.element || !page) return null;
  let domainId: string | null = null;
  try { domainId = domainForNode(graph, page.id)?.id ?? null; } catch { return null; }
  if (!domainId) return null;
  const sections = page.site?.kind === "page" ? page.site.sections ?? [] : [];
  const section = sections.find((item) => item.id === node.card?.section);
  return { nodeId, kind: logicLook(node.element.kind).label, name: node.name.trim() || "Bez názvu", pageId: page.id, page: page.name,
    box: section ? section.name : null, domainId };
}

/** Titulek plátna logiky prvku: plátno je specializované na logiku a tok dat jednoho prvku. */
export const logicCanvasTitle = (context: Pick<ElementContext, "name">) => `Logika a tok dat · ${context.name}`;

/** Výzva prázdného plátna logiky prvku: co sem patří, místo prázdna. */
export const LOGIC_PROMPT = {
  title: "Jak prvek funguje: vstupy → kroky → výstupy",
  lead: "Sem patří, s čím prvek začíná (vstupy, data), co se s tím děje krok po kroku, za jakých podmínek se cesta větví a co vyjde ven (výstupy, služby). Popište to, nebo přetáhněte uzly z palety.",
} as const;

/** Adresa návratu na plán stránky: doména, stránka a vybraný prvek; identita editoru se dopočítá znovu (jiná doména). */
export function planRoute(search: string, context: ElementContext): URLSearchParams {
  const route = new URLSearchParams(search);
  route.set("domainId", context.domainId); route.set("pageId", context.pageId); route.set("architectureNode", context.nodeId);
  route.delete("editorId"); route.delete("flow"); route.set("projectView", "architecture");
  return route;
}
