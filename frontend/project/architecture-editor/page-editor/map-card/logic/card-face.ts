// Co karta mapy ukazuje kromě stavu, jako karta Studia: druh a podtitulek (cesta podstránky, technologie uzlu) a barva
// portů podle toho, co po jejich vazbách teče (`carries`, převládající druh jako souhrnná vazba Studia). Volný port
// (bez vazby) je `null` a kreslí se jako prázdný kroužek. Čistá logika bez Reactu.
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import { canCarry } from "@/shared/edge-carries/logic/edge-carries";
import { dominantFlow, type StudioFlow } from "@/project/studio/logic/studio-level";

export type CardPorts = { in: StudioFlow | null; out: StudioFlow | null };

/** Druh toku vazeb, které do karty vcházejí (`in`) nebo z ní vycházejí (`out`); bez vazby null. */
export function portFlow(edges: GraphEdge[], nodeId: string, side: "in" | "out"): StudioFlow | null {
  const own = edges.filter((edge) => (side === "in" ? edge.target : edge.source) === nodeId);
  if (!own.length) return null;
  const kinds: Partial<Record<StudioFlow, number>> = {};
  for (const edge of own) if (canCarry(edge) && edge.carries) kinds[edge.carries] = (kinds[edge.carries] ?? 0) + 1;
  return dominantFlow(kinds);
}

export const cardPorts = (edges: GraphEdge[], nodeId: string): CardPorts => ({ in: portFlow(edges, nodeId, "in"), out: portFlow(edges, nodeId, "out") });

/** Druh karty a její adresa drobně pod hlavičkou: podstránka a cesta, sektor, uzel a technologie. */
export function cardFace(node: CanvasNode): { kind: string; subtitle: string } {
  if (node.site?.kind === "page") return { kind: "Podstránka", subtitle: node.site.path };
  return { kind: node.kind === "sector" ? "Sektor" : "Uzel", subtitle: node.card?.tech ?? "" };
}
