// Převzatá plátna projektu pro karty domén a stránek. Karta stránky je rekurzivní a karta domény leží o tři vrstvy
// níž než editor, proto data jdou kontextem (jako `PortActionsContext` editoru toků), ne přes props každé vrstvy.
import { createContext } from "react";
import type { ProjectFlow } from "./project-flows";

export type ProjectFlowsValue = { flows: ReadonlyMap<string, ProjectFlow[]>; onOpen?: (flowId: string) => void };
export const ProjectFlowsContext = createContext<ProjectFlowsValue>({ flows: new Map() });
