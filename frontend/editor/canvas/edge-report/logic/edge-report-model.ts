// Čistý model zprávy agenta na vazbě: vazba je místo, kam se zapisuje, co se udělalo při přechodu
// z jedné karty (bloku) na další. Bez Reactu; panel jen zobrazuje a bublá změny, ukládá rodič (App).
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import { isBlockEdge } from "@/shared/types/logic/types";
import type { DesktopState, EdgeReport, EdgeReportField, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { blockPorts, edgeReports, MAX_REPORT_FIELD } from "@/shared/desktop-state/logic/types";
import { cardAddress } from "@/shared/card-context/logic/card-context";

/** Pět pojmenovaných textových polí zprávy; podpis (`updatedAt`, `by`, `agent`) se dopisuje sám. */
export const REPORT_FIELDS: EdgeReportField[] = ["log", "summary", "handoff", "improvements", "errors"];

export const emptyReport = (): EdgeReport => ({
  log: "", summary: "", handoff: "", improvements: "", errors: "", updatedAt: "", by: "human", agent: "",
});

/** Zpráva vazby s doplněnými poli; starší stav bez sekce `edges` vrací prázdnou zprávu. */
export function reportOf(state: DesktopState, edgeId: string): EdgeReport {
  return { ...emptyReport(), ...(edgeReports(state)[edgeId] ?? {}) };
}

/**
 * Zápis zprávy: doplní jen poslaná pole, ostatní (i `sentAt` a `due`) nechá být, orazítkuje `updatedAt`
 * a podepíše `by: "human"`. Agent píše do téže sekce přes `agent-output`, proto je `by` součástí zprávy,
 * ne odvozené z místa zápisu. Změna neprázdného `handoff` nastaví `sentAt` na čas zápisu (§4) — ručně
 * se `sentAt` nastavit nedá, jen zachovat.
 */
export const setEdgeReport = (edgeId: string, patch: Partial<EdgeReport>) => (state: DesktopState): DesktopState => {
  const before = reportOf(state, edgeId);
  const updatedAt = patch.updatedAt ?? new Date().toISOString();
  const next: EdgeReport = {
    ...before,
    ...patch,
    by: patch.by ?? "human",
    updatedAt,
  };
  if (handoffSent(before, patch)) next.sentAt = updatedAt;
  for (const field of REPORT_FIELDS) next[field] = next[field].slice(0, MAX_REPORT_FIELD);
  return { ...state, edges: { ...edgeReports(state), [edgeId]: next } };
};

/** Předání se odeslalo, když zápis mění `handoff` na neprázdný text, jiný než dosud. */
export function handoffSent(before: Pick<EdgeReport, "handoff">, patch: Partial<EdgeReport>): boolean {
  return patch.handoff !== undefined && patch.handoff.trim() !== "" && patch.handoff !== before.handoff;
}

/** Odkud a kam vazba vede: název a čitelná adresa obou karet (jen ke čtení, počítá se z grafu). */
export type EdgeRoute = { from: { name: string; address: string }; to: { name: string; address: string } };

export function edgeRoute(edge: Pick<GraphEdge, "source" | "target">, nodes: Pick<CanvasNode, "id" | "name" | "parentId">[]): EdgeRoute {
  const end = (id: string) => {
    const node = nodes.find((n) => n.id === id);
    return node ? { name: node.name, address: cardAddress(nodes, node) } : { name: id, address: "" };
  };
  return { from: end(edge.source), to: end(edge.target) };
}

/** Kdy se předalo, pro člověka: `2. 10. 2026 14:05` v místním čase; chybí = „nepředáno“. */
export function formatSent(sentAt: string | undefined): string {
  if (!sentAt) return "nepředáno";
  const date = new Date(sentAt);
  if (Number.isNaN(date.getTime())) return sentAt;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getDate()}. ${date.getMonth() + 1}. ${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Co panel vazby zobrazí v hlavě: odkud kam, z jakého portu a — u vazby z bloku — z kterého tlačítka. */
export type EdgeReportView = {
  edgeId: string;
  sourceName: string;
  targetName: string;
  portLabel: string;
  blockNumber: string;
  blockTitle: string;
  portName: string;
};

const PORT_LABEL: Record<string, string> = { next: "DALŠÍ KROK", action: "AKCE", rule: "PRAVIDLA", block: "PORT BLOKU", flow: "TOK MEZI OBLASTMI" };

export function edgeReportView(
  edge: GraphEdge,
  nodes: Pick<CanvasNode, "id" | "name">[],
  workflow: Pick<NodeWorkflowFull, "blocks">,
): EdgeReportView {
  const nameOf = (id: string) => nodes.find((n) => n.id === id)?.name ?? id;
  const block = isBlockEdge(edge) ? workflow.blocks.find((b) => b.id === edge.sourceBlockId) : undefined;
  const port = block && isBlockEdge(edge) ? blockPorts(block).find((p) => p.id === edge.sourcePortId) : undefined;
  return {
    edgeId: edge.id,
    sourceName: nameOf(edge.source),
    targetName: nameOf(edge.target),
    portLabel: PORT_LABEL[edge.port ?? "next"] ?? "DALŠÍ KROK",
    blockNumber: block?.number ?? "",
    blockTitle: block?.title ?? "",
    portName: port?.label ?? "",
  };
}

/** Kolik z pěti polí je vyplněno; nula znamená „na této vazbě zatím nikdo nic nevysvětlil“. */
export function filledFields(report: EdgeReport): number {
  return REPORT_FIELDS.filter((field) => report[field].trim()).length;
}

/** Podpis pod zprávou: kdo naposledy psal a kdy. Nedotčená zpráva se nepodepisuje. */
export function reportSignature(report: EdgeReport): string {
  if (!report.updatedAt) return "";
  const who = report.by === "agent" ? `agent${report.agent ? ` ${report.agent}` : ""}` : "člověk";
  return `${who} · ${report.updatedAt}`;
}
