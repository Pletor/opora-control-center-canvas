// Barva a fáze prvku v Detailu: vrstva karty (`neutral`, když ji karta nemá) a české popisky pracovních fází.
import type { CanvasNode, CardLayer } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";

export type Tone = CardLayer | "neutral";
export const toneOf = (node: CanvasNode): Tone => node.card?.layer ?? "neutral";

export const PHASE_LABEL: Record<NodePhase, string> = {
  discover: "Průzkum",
  define: "Zadání",
  build: "Stavba",
  verify: "Ověření",
  live: "Provoz",
};
