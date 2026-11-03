// Kanál z karty uzlu na plátno: „+“ u portu otevře paletu předfiltrovanou na kind portu. Karta je uzel React Flow
// a props od rodiče nedostává přímo, proto jde akce přes kontext (stejně jako `CardActionsContext` ve Studiu).
import { createContext } from "react";
import type { PortKind, PortRef } from "../../logic/flow-types";

export type PlusRequest = PortRef & { kind: PortKind };
export const PortActionsContext = createContext<{ onPlus: (request: PlusRequest) => void }>({ onPlus: () => {} });
