// Vazby `next` mezi kartami jako graf závislostí (docs/oporahub-agent-state.md, „Graf karet“): z hotového
// předchůdce (sloučeno a zapsáno, nebo uzavřeno) vede plná zelená čára — cesta je volná; jinak přerušovaná,
// protože navazující karta na předchůdce ještě čeká. Rozhoduje tvář karty z agent-state, ne odhad plátna.
import type { Edge } from "@xyflow/react";
import type { GraphEdge } from "@/shared/types/logic/types";
import { carriesLook } from "@/shared/edge-carries/logic/edge-carries";

export function dagLook(edge: GraphEdge, cards: ReadonlySet<string>, finished: ReadonlySet<string>): Partial<Edge> | null {
  if (edge.relation || (edge.port ?? "next") !== "next" || !cards.has(edge.source) || !cards.has(edge.target)) return null;
  // Druh toku (`carries`) drží barvu a háček třídy; stav závislosti říká jen čára: volno plná, čeká přerušovaná.
  const flow = carriesLook(edge.carries);
  const hook = flow ? " " + flow.className : "";
  return finished.has(edge.source)
    ? { style: { stroke: flow?.stroke ?? "var(--ok)", strokeWidth: 2.5 + (flow?.extraWidth ?? 0) }, className: "edge-port-next edge-dag--open" + hook }
    : { style: { stroke: flow?.stroke ?? "var(--ink-muted)", strokeWidth: 1.5 + (flow?.extraWidth ?? 0), strokeDasharray: "6 5" }, className: "edge-port-next edge-dag--waiting" + hook };
}
