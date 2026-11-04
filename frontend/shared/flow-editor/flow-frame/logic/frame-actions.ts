// Kanál z poznámky a rámce na plátně do editoru: uzel React Flow nedostává props od rodiče přímo, proto akce jdou přes
// kontext (stejně jako „+“ u portu v `flow-node/logic/port-actions.ts`).
import { createContext } from "react";
import type { FlowNote } from "../../logic/flow-types";

export type FrameActions = {
  onNote: (id: string, patch: Partial<Omit<FlowNote, "id">>) => void;
  onToggleGroup: (id: string) => void;
};
export const FrameActionsContext = createContext<FrameActions>({ onNote: () => {}, onToggleGroup: () => {} });

/** Barvy poznámek jako sedm předvoleb n8n (1 žlutá … 7 šedá); barva je číslo v grafu, odstín dodá styl. */
export const NOTE_COLORS = [1, 2, 3, 4, 5, 6, 7] as const;
