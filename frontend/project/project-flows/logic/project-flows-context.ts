// Převzatá plátna projektu pro karty domén a stránek a plátna logiky prvků plátna 2. Karta stránky je rekurzivní,
// karta domény i štítek prvku leží o několik vrstev níž než editor, proto data jdou kontextem (jako
// `PortActionsContext` editoru toků), ne přes props každé vrstvy. Kontext nastaví `ProjectFlowsProvider`.
import { createContext } from "react";
import type { ProjectFlow } from "./project-flows";

export type ProjectFlowsValue = {
  flows: ReadonlyMap<string, ProjectFlow[]>; onOpen?: (flowId: string) => void;
  /** Nastavit logiku prvku: plátno existuje = otevře ho, jinak okno Prázdné plátno / Z knihovny. */
  onSetLogic?: (node: { id: string; name: string }) => void;
  /** Dvojklik na prvek: plátno existuje = otevře ho, jinak založí prázdné a otevře (bez okna). */
  onOpenLogic?: (node: { id: string; name: string }) => void;
};
export const ProjectFlowsContext = createContext<ProjectFlowsValue>({ flows: new Map() });
