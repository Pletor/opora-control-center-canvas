import type { Graph } from "@/shared/types/logic/types";
import { architectureEditorId, editorScopeNode, validateEditorRoute } from "./editor-model";
import { domainForNode, domainNode } from "./domain-model";

// Adresa editoru architektury → otevřená doména, stránka a vybraný prvek. Starší parametr `structureNode` se ignoruje.
// Neplatný odkaz vyhodí větu pro člověka; nic se tiše nepřesměruje.

export type EditorRoute = { domainId: string | null; pageId: string | null; selectedId: string | null };

export function resolveEditorRoute(graph: Graph, route: URLSearchParams, project: string, workspace: string): EditorRoute {
  let domainId = route.get("domainId"); let pageId = route.get("pageId");
  if (route.has("domainId") && !domainId) throw new Error("Odkaz neobsahuje platné ID domény.");
  if (!domainId && pageId) domainId = domainForNode(graph, pageId)?.id ?? null;
  if (pageId && !domainId) throw new Error("Tato část nepatří do žádné domény. Otevřete ji v běžném Editoru.");
  if (domainId) domainNode(graph, domainId);
  const supplied = route.get("editorId");
  if (!route.has("domainId") && supplied === architectureEditorId(project, workspace)) validateEditorRoute(supplied, project, workspace);
  else validateEditorRoute(supplied, project, workspace, domainId ?? undefined);
  if (pageId) {
    editorScopeNode(graph, pageId);
    if (domainForNode(graph, pageId)?.id !== domainId) throw new Error("Stránka nepatří k doméně v odkazu.");
    if (pageId === domainId) pageId = null;
  }
  const selectedId = route.get("architectureNode") ?? pageId;
  if (selectedId && domainForNode(graph, selectedId)?.id !== domainId) throw new Error("Vybraný prvek nepatří k doméně v odkazu.");
  return { domainId, pageId, selectedId };
}
