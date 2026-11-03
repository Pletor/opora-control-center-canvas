// Log běhu jako řádky pro spodní panel: append-only události (`log_event`) s uzlem dohledaným přes `node_run_id`,
// lidským popisem, plátnem (1–4) a tónem. Klik na řádek s uzlem vybere uzel na plátně; vybraný uzel zvýrazní své
// řádky (synchronizace log ↔ plátno).
import type { LogEvent, NodeRun } from "@/shared/flow-editor/logic/flow-types";

export type LogTone = "plain" | "ok" | "bad" | "wait";
export type LogRow = { seq: number; time: string; type: string; nodeId: string | null; text: string; canvas: number; tone: LogTone };

const obj = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const short = (value: unknown, max = 120) => {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text && text.length > max ? text.slice(0, max - 1) + "…" : text ?? "";
};

function describe(event: LogEvent): { text: string; tone: LogTone } {
  const p = obj(event.payload);
  switch (event.type) {
    case "run.created": return { text: `běh vznikl · ${short([obj(p.trigger).source, obj(p.trigger).node_id].filter(Boolean).join(" · ") || "ruční")}`, tone: "plain" };
    case "run.status": return { text: `běh: ${String(p.status)}`, tone: p.status === "failed" ? "bad" : p.status === "succeeded" ? "ok" : "plain" };
    case "node.queued": return { text: `ve frontě · pokus ${String(p.attempt ?? 1)}`, tone: "plain" };
    case "node.started": return { text: "start", tone: "plain" };
    case "node.heartbeat": return { text: "heartbeat", tone: "plain" };
    case "node.waiting": return { text: `čeká na ${String(p.waiting_for ?? "?")}${p.deadline ? ` do ${String(p.deadline)}` : ""}`, tone: "wait" };
    case "node.succeeded": return { text: `hotovo → ${String(p.port ?? "main")}${p.cost_usd ? ` · ${String(p.cost_usd)} $` : ""}${p.model ? ` · ${String(p.model)}` : ""}`, tone: "ok" };
    case "node.failed": return { text: `chyba: ${short(p.error)}`, tone: "bad" };
    default: return { text: short(event.payload), tone: event.type.includes("error") ? "bad" : "plain" };
  }
}

export function logRows(events: readonly LogEvent[], nodeRuns: readonly NodeRun[]): LogRow[] {
  const nodeOf = new Map(nodeRuns.map((run) => [run.id, run.node_id]));
  return events.map((event) => {
    const fromPayload = obj(event.payload).node_id;
    const nodeId = (event.node_run_id && nodeOf.get(event.node_run_id)) || (typeof fromPayload === "string" ? fromPayload : null);
    const at = new Date(event.ts);
    return { seq: event.seq, time: Number.isNaN(at.getTime()) ? event.ts : at.toLocaleTimeString("cs-CZ"), type: event.type, nodeId, canvas: event.canvas, ...describe(event) };
  });
}
