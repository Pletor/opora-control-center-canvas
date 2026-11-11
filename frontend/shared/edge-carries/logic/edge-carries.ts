// Druh toku vazby `carries` (docs/architektura-pro-agenty.md §3.4): české popisky, pravidlo „jen vazba next“
// a jemné statické odlišení čáry. Sdílí ho plátno karet (board-model) a Detail prvku.
import type { EdgeCarries, GraphEdge } from "@/shared/types/logic/types";
import { EDGE_CARRIES } from "@/shared/types/logic/types";

/** Česky pro člověka: volba v detailu prvku, popisek a tooltip vazby. */
export const CARRIES_LABEL: Record<EdgeCarries, string> = {
  navigation: "Navigace", data: "Data", command: "Příkaz", event: "Událost",
};

/** `carries` smí nést jen vazba `next` (i bez portu); stejné pravidlo hlídá backend `graph.py`. */
export const canCarry = (edge: Pick<GraphEdge, "port">): boolean => (edge.port ?? "next") === "next";

/** Hodnota z výběru: prázdná nebo neznámá znamená „neurčeno“ (klíč se z vazby odebere). */
export function parseCarries(value: string): EdgeCarries | null {
  return (EDGE_CARRIES as string[]).includes(value) ? (value as EdgeCarries) : null;
}

/** Statický vzhled druhu toku (docs/zive-zobrazeni-a-knihovna.md §2): barva je token `--edge-carries-<druh>`
 *  z `design-tokens/styles/theme-tokens.css`, `extraWidth` se přičte k základní šířce čáry daného plátna. */
export type CarriesLook = {
  /** Háček pro pozdější animaci toku: `edge--carries-<druh>`. */
  className: string;
  stroke: string;
  dash?: string;
  extraWidth: number;
  /** Druh toku česky pro tooltip a čtečky; na čáře se nepíše. */
  title: string;
};

/** Navigace, data a příkaz plnou čarou (příkaz o 0,5 px silnější), událost čárkovaně `6 4`. */
const LINE: Record<EdgeCarries, { dash?: string; extraWidth: number }> = {
  navigation: { extraWidth: 0 },
  data: { extraWidth: 0 },
  command: { extraWidth: 0.5 },
  event: { dash: "6 4", extraWidth: 0 },
};

/** Vzhled vazby s druhem toku; bez `carries` (neurčeno) `null` a vazba vypadá jako dnes. */
export function carriesLook(carries: EdgeCarries | undefined): CarriesLook | null {
  if (!carries || !Object.hasOwn(LINE, carries)) return null;
  return {
    className: `edge--carries-${carries}`, stroke: `var(--edge-carries-${carries})`, ...LINE[carries],
    title: `Po vazbě teče: ${CARRIES_LABEL[carries]}`,
  };
}
