// Převod úrovně Studia na uzly a hrany React Flow: karty na polohách z `layoutLevel`, rám skupiny „bez sekce“ pod nimi
// a souhrnné vazby jako hrany typu `studio-link` s počtem a druhem toku. Uzly nesou pevné rozměry: plátno je řízené bez
// `onNodesChange`, takže změřené rozměry se do uzlů nevrací a minimapa i fit by bez nich karty neviděly.
// Čistá logika bez Reactu; plátno ji jen předá.
import type { Edge, Node } from "@xyflow/react";
import type { StudioFlow, StudioLink } from "../../logic/studio-level";
import type { StudioCardView } from "../../studio-card/logic/card-view";
import { CARRIES_LABEL } from "@/shared/edge-carries/logic/edge-carries";
import { CARD_HEIGHT, CARD_WIDTH, type StudioLayout } from "./studio-layout";

export type StudioLinkData = { count: number; carries: StudioFlow; title: string };
export type StudioLinkEdge = Edge<StudioLinkData, "studio-link">;
export const FLOW_LABEL: Record<StudioFlow, string> = { ...CARRIES_LABEL, unspecified: "Neurčeno" };
export const UNSECTIONED_LABEL = "Bez sekce";

/** Popisek vazby pro tooltip a čtečku: druh toku a z kolika hran se skládá („Navigace · 3 vazby“). */
export function linkTitle(link: Pick<StudioLink, "count" | "carries" | "kinds">): string {
  const mixed = Object.keys(link.kinds).length > 1 ? " (" + Object.entries(link.kinds).map(([kind, count]) => `${FLOW_LABEL[kind as StudioFlow]} ${count}`).join(", ") + ")" : "";
  return `${FLOW_LABEL[link.carries]} · ${link.count} ${link.count === 1 ? "vazba" : link.count < 5 ? "vazby" : "vazeb"}${mixed}`;
}

export function flowNodes<Data extends Record<string, unknown>>(views: StudioCardView[], layout: StudioLayout, selected: string | null, data: (view: StudioCardView) => Data): Node[] {
  const nodes: Node[] = [];
  if (layout.group) nodes.push({
    id: layout.group.id, type: "studio-group", position: { x: layout.group.x, y: layout.group.y }, data: { label: UNSECTIONED_LABEL },
    width: layout.group.width, height: layout.group.height, selectable: false, draggable: false, focusable: false, zIndex: -1,
  });
  for (const view of views) {
    const position = layout.positions.get(view.id);
    if (position) nodes.push({ id: view.id, type: "studio-card", position, width: CARD_WIDTH, height: CARD_HEIGHT, data: data(view), selected: view.id === selected, draggable: false, connectable: false });
  }
  return nodes;
}

export function flowEdges(links: StudioLink[]): StudioLinkEdge[] {
  return links.map((link) => ({
    id: link.id, source: link.source, target: link.target, type: "studio-link", focusable: false, selectable: false,
    data: { count: link.count, carries: link.carries, title: linkTitle(link) },
  }));
}
