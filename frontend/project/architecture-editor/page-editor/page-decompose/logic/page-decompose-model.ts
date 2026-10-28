// Podklady rozkladu stránky (docs/architektura-pro-agenty.md §5.2): z grafu a kontroly mapy vybere, co agent potřebuje,
// aby stránku rozložil sám – stránku s cílem a sekcemi, cesty zákazníka přes stránku, existující komponenty a díry.
// Čistá logika bez Reactu, test vedle; text zadání z nich skládá `page-decompose-prompt.ts`. Nic se neodhaduje:
// chybějící údaj chybí i v podkladech.
import type { CanvasNode, EdgeCarries, Graph, PageSection } from "@/shared/types/logic/types";
import { domainForNode } from "../../../logic/domain-model";
import { lineage, type MapCheck, type MapCheckFinding } from "../../../domain-map/map-check/logic/map-check";
import { pageSlices, type PageSlice } from "../../journey-slice/logic/page-slice";

/** Komponenta stránky: uzel, jehož nejbližší stránka je rozkládaná stránka, s vazbami ven i dovnitř, které nesou `carries`. */
export type DecomposeComponent = {
  id: string; name: string; section?: string; tech?: string; states?: string[];
  out: { carries: EdgeCarries; to: string }[]; in: { carries: EdgeCarries; from: string }[];
};
export type DecomposeFacts = {
  pageId: string; name: string; path: string; goal?: string; feel?: string;
  sections: PageSection[]; journeys: PageSlice[]; components: DecomposeComponent[];
  /** Nálezy kontroly mapy stránky; `null` = kontrola zatím nenačtená (zadání to řekne a agent si ji přečte sám). */
  holes: MapCheckFinding[] | null;
};

/** Zprávy nálezů přechodu cesty (backend `map_check.py`), které vycházejí ze stránky s cestou `path`. */
const JOURNEY_HOLES: Record<string, (path: string) => string> = {
  "journey.unrealized": (path) => ` z ${path} na `,
  "journey.via-unknown": (path) => ` stránka ${path} nemá`,
};

/** Nejbližší stránka uzlu (sám, nebo předek se `site.kind = "page"`); aplikace je hranice. */
function pageOf(byId: Map<string, CanvasNode>, id: string): string | null {
  for (const node of lineage(byId, id)) {
    if (node.site?.kind === "page") return node.id;
    if (node.site?.kind === "application") return null;
  }
  return null;
}

/**
 * Díry stránky: nález na stránku nebo její komponentu, na hranu z nich, a nález přechodu cesty, který ze stránky
 * vychází (`unrealized` „z /a na /b“, `via-unknown` „stránka /a nemá“) na cestě přes stránku. Pořadí kontroly mapy zůstává.
 */
export function pageHoles(check: MapCheck, graph: Graph, pageId: string, journeyIds: ReadonlySet<string>): MapCheckFinding[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const page = byId.get(pageId);
  const path = page?.site?.kind === "page" ? page.site.path : "";
  const mine = (id: string | undefined) => !!id && pageOf(byId, id) === pageId;
  return check.findings.filter((finding) => {
    if (finding.nodeId) return mine(finding.nodeId);
    if (finding.edgeId) return mine(graph.edges.find((edge) => edge.id === finding.edgeId)?.source);
    const marker = JOURNEY_HOLES[finding.rule];
    return !!finding.journeyId && journeyIds.has(finding.journeyId) && !!marker && !!path && finding.message.includes(marker(path));
  });
}

/** Komponenty stránky v pořadí grafu; podstránky (a vše pod nimi) mají svou stránku, proto sem nepatří. */
export function pageComponents(graph: Graph, pageId: string): DecomposeComponent[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const name = (id: string) => byId.get(id)?.name.trim() || id;
  return graph.nodes.filter((node) => node.id !== pageId && node.kind === "node" && pageOf(byId, node.id) === pageId).map((node) => {
    const card = node.card ?? {};
    return {
      id: node.id, name: node.name,
      ...(card.section ? { section: card.section } : {}), ...(card.tech ? { tech: card.tech } : {}),
      ...(card.states?.length ? { states: [...card.states] } : {}),
      out: graph.edges.flatMap((edge) => edge.source === node.id && edge.carries ? [{ carries: edge.carries, to: name(edge.target) }] : []),
      in: graph.edges.flatMap((edge) => edge.target === node.id && edge.carries ? [{ carries: edge.carries, from: name(edge.source) }] : []),
    };
  });
}

/** Podklady rozkladu stránky `pageId`; `null`, když uzel není stránka. */
export function pageDecomposeFacts(graph: Graph, pageId: string, check: MapCheck | null): DecomposeFacts | null {
  const page = graph.nodes.find((node) => node.id === pageId);
  if (!page || page.site?.kind !== "page") return null;
  let app: CanvasNode | null = null;
  try { app = domainForNode(graph, pageId); } catch { app = null; }
  const site = app?.site?.kind === "application" ? app.site : undefined;
  const journeys = pageSlices(site, pageId, graph.nodes);
  return {
    pageId, name: page.name, path: page.site.path,
    ...(page.site.goal ? { goal: page.site.goal } : {}), ...(page.site.feel ? { feel: page.site.feel } : {}),
    sections: page.site.sections ?? [], journeys, components: pageComponents(graph, pageId),
    holes: check ? pageHoles(check, graph, pageId, new Set(journeys.map((slice) => slice.journeyId))) : null,
  };
}
