// Akce karty MODELu předané plátnem přes kontext (data uzlů React Flow zůstávají čistá a porovnatelná): stisk portu
// začne klik nebo tah vazby, klávesa Enter / mezerník na portu je klik pro klávesnici.
import { createContext, type PointerEvent } from "react";

export type CardActions = {
  onPortDown: (nodeId: string, portId: string, event: PointerEvent) => void;
  onPortKey: (nodeId: string, portId: string) => void;
};

export const CardActionsContext = createContext<CardActions>({ onPortDown: () => undefined, onPortKey: () => undefined });
