// Vazby `next` mezi kartami jako graf závislostí (docs/oporahub-agent-state.md, „Graf karet“): z hotového
// předchůdce (sloučeno a zapsáno, nebo uzavřeno) vede plná zelená čára — cesta je volná; jinak přerušovaná,
// protože navazující karta na předchůdce ještě čeká. Rozhoduje tvář karty z agent-state, ne odhad plátna.
import type { Edge } from "@xyflow/react";
import type { GraphEdge } from "@/shared/types/logic/types";

export function dagLook(edge: GraphEdge, cards: ReadonlySet<string>, finished: ReadonlySet<string>): Partial<Edge> | null {
  if ((edge.port ?? "next") !== "next" || !cards.has(edge.source) || !cards.has(edge.target)) return null;
  return finished.has(edge.source)
    ? { style: { stroke: "var(--ok)", strokeWidth: 2.5 }, className: "edge-port-next edge-dag--open" }
    : { style: { stroke: "var(--ink-muted)", strokeWidth: 1.5, strokeDasharray: "6 5" }, className: "edge-port-next edge-dag--waiting" };
}
