import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { AcceptedResult } from "@/editor/llm-control/editor-context/logic/handoff";

export type DnaTimelineGroup = "Zadání" | "Práce" | "Ověření" | "Předávky" | "Kód";
export type DnaTimelineItem = { at: string; group: DnaTimelineGroup; label: string; detail?: string; source: string };
export type DnaHistoryInput = { node: CanvasNode; data: NodeCardData; state: DesktopState; graph: Graph; brief?: Record<string, unknown> | null; results: AcceptedResult[]; messages?: Record<string, unknown>[] };
const record = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const text = (value: unknown): string => typeof value === "string" ? value : "";
const rowsOf = (value: unknown): Record<string, unknown>[] => Array.isArray(record(value).messages) ? record(value).messages as Record<string, unknown>[] : [];

/** Časová osa skládá uložené stopy z obou směrů, neodvozuje žádný nezaznamenaný krok. */
export function buildDnaTimeline(input: DnaHistoryInput): DnaTimelineItem[] {
  const { node, data, state, graph, brief, results } = input; const workflow = state.nodes[node.id]; const communication = record(record(brief).communication);
  const messages = input.messages ? input.messages.map(item => ({ item, side: text(item.targetNodeId) === node.id ? "Příchozí" : "Odchozí" })) : [...rowsOf(communication.incoming).map(item => ({ item, side: "Příchozí" })), ...rowsOf(communication.outgoing).map(item => ({ item, side: "Odchozí" }))];
  const rows: DnaTimelineItem[] = [
    ...results.flatMap(result => result.specification ? [{ at: result.createdAt, group: "Zadání" as const, label: "Snímek zadání", detail: JSON.stringify(result.specification), source: `agent-result:${result.id}:assignment` }] : []),
    ...(data.work?.startedAt ? [{ at: data.work.startedAt, group: "Práce" as const, label: `Převzetí · ${data.work.agent || "agent"}`, source: "work" }] : []),
    ...(data.lease?.active ? [{ at: "", group: "Práce" as const, label: `Aktivní lease · ${data.lease.owner}`, source: "lease" }] : []),
    ...(workflow?.stages?.items ?? []).flatMap(stage => stage.at ? [{ at: stage.at, group: stage.kind === "work" || stage.kind === "fix" ? "Práce" as const : "Ověření" as const, label: `Etapa · ${stage.title}`, detail: [stage.status, stage.note, stage.retryOf ? `opakování ${stage.retryOf}` : ""].filter(Boolean).join(" · "), source: `stage:${stage.id}` }] : []),
    ...results.map(result => ({ at: result.createdAt, group: "Práce" as const, label: `Výstup agenta · ${result.agent || "agent"}`, detail: result.binding, source: `agent-result:${result.id}` })),
    ...state.decisions.filter(item => item.nodeId === node.id).map(item => ({ at: item.createdAt, group: "Předávky" as const, label: "Rozhodnutí", detail: item.text, source: `decision:${item.id}` })),
    ...messages.map(({ item, side }, index) => { const sender = text(item.senderLabel) || "agent"; return { at: text(item.createdAt) || text(item.at), group: "Předávky" as const, label: `${side} zpráva · ${sender}`, detail: text(item.text) || text(item.body) || text(item.summary), source: `message:${side}:${text(item.id) || index}` }; }),
    ...graph.edges.filter(edge => edge.source === node.id || edge.target === node.id).flatMap(edge => { const item = state.edges?.[edge.id]; return item?.updatedAt ? [{ at: item.updatedAt, group: "Předávky" as const, label: "Zpráva na vazbě", detail: item.handoff || item.summary || item.log, source: `edge:${edge.id}` }] : []; }),
    ...(data.evidence?.checksRun ?? []).map(run => ({ at: run.at, group: "Ověření" as const, label: `Kontrola · ${run.checkId}`, detail: `${run.command || "nedoloženo"} · exit ${run.exitCode ?? "nedoloženo"}`, source: `check:${run.checkId}:${run.at}` })),
    ...(node.realization?.verifiedAt ? [{ at: node.realization.verifiedAt, group: "Kód" as const, label: `Realizace · ${node.realization.commit || "nedoloženo"}`, detail: node.realization.prUrl, source: "realization" }] : []),
  ];
  return rows.slice().sort((left, right) => { const a = Date.parse(left.at); const b = Date.parse(right.at); if (Number.isNaN(a)) return Number.isNaN(b) ? 0 : 1; if (Number.isNaN(b)) return -1; return a - b; });
}
export function filterDnaTimeline(rows: DnaTimelineItem[], group: DnaTimelineGroup | "Vše"): DnaTimelineItem[] { return group === "Vše" ? rows : rows.filter(row => row.group === group); }
