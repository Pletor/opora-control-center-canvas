// Klient pro GET/POST /api/node-sessions přesně dle CONTRACT.md (node-live-20260911).
// Žádné vymyšlené stavy, procenta pokroku ani obsah zpráv — jen bezpečná metadata ze zdroje.
import { api } from "@/shared/types/logic/types";

export type NodeSessionSource = "hermes" | "claude";
export type NodeSessionRole = "orchestrator" | "worker";
export type NodeSessionStatus = "running" | "recent_activity" | "idle" | "completed" | "failed" | "unknown";

export type SessionEvent = { id: string; at: string | null; kind: string; summary: string };

export type NodeSessionMetrics = { inputTokens: number | null; outputTokens: number | null; costUsd: number | null };

export type NodeSession = {
  id: string;
  source: NodeSessionSource;
  sessionId: string;
  parentSessionId: string | null;
  role: NodeSessionRole;
  title: string;
  project: string;
  workspace: string;
  nodeId: string;
  nodeName: string;
  model: string | null;
  status: NodeSessionStatus;
  statusReason: string;
  sourceAvailable: boolean;
  lastActivityAt: string | null;
  boundAt: string;
  closedAt: string | null;
  events: SessionEvent[];
  metrics: NodeSessionMetrics;
  sourceLabel: string;
};

export type NodeSessionsResponse = {
  project: string;
  workspace: string;
  nodeId: string | null;
  sessions: NodeSession[];
  limit: number;
  truncated: boolean;
};

/** Čte skutečné vázané sessions pro rozsah; volitelně omezené na jeden uzel. Signal umožňuje
 * zrušit dotaz při opuštění panelu nebo změně rozsahu (ochrana proti zastaralé odpovědi). */
export async function fetchNodeSessions(
  project: string,
  workspace: string,
  nodeId: string | undefined,
  signal: AbortSignal,
): Promise<NodeSessionsResponse> {
  const params = new URLSearchParams({ project, workspace });
  if (nodeId) params.set("nodeId", nodeId);
  const url = `/api/node-sessions?${params}`;
  const response = await fetch(url, { signal });
  const raw = await response.text();
  let value: Record<string, unknown>;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(`Zdroj sessions není dostupný (HTTP ${response.status}).`);
  }
  if (!value || typeof value !== "object") throw new Error("Zdroj vrátil neplatnou odpověď.");
  if (!response.ok) {
    throw new Error(typeof value.error === "string" ? value.error : `Požadavek na sessions se nezdařil (HTTP ${response.status}).`);
  }
  if (!Array.isArray(value.sessions) || value.sessions.length > 100) throw new Error("Zdroj nevrátil platný seznam sessions.");
  if (value.project !== project || value.workspace !== workspace || value.nodeId !== (nodeId ?? null)) {
    throw new Error("Odpověď neodpovídá zvolenému rozsahu.");
  }
  const isText = (v: unknown) => typeof v === "string";
  const nullableText = (v: unknown) => v === null || isText(v);
  const numeric = (v: unknown) => v === null || (typeof v === "number" && Number.isFinite(v) && v >= 0);
  const valid = value.sessions.every((s: NodeSession) => s && typeof s === "object"
    && [s.id,s.sessionId,s.title,s.nodeId,s.nodeName,s.statusReason,s.sourceLabel,s.boundAt].every(isText)
    && s.project === project && s.workspace === workspace && (!nodeId || s.nodeId === nodeId)
    && ["hermes","claude"].includes(s.source) && ["worker","orchestrator"].includes(s.role)
    && ["running","recent_activity","idle","completed","failed","unknown"].includes(s.status)
    && [s.model,s.parentSessionId,s.lastActivityAt,s.closedAt].every(nullableText)
    && typeof s.sourceAvailable === "boolean" && s.metrics && typeof s.metrics === "object"
    && [s.metrics.inputTokens,s.metrics.outputTokens,s.metrics.costUsd].every(numeric)
    && Array.isArray(s.events) && s.events.length <= 50
    && s.events.every(e => e && [e.id,e.kind,e.summary].every(isText) && nullableText(e.at)));
  if (!valid) throw new Error("Zdroj vrátil neplatná metadata sessions.");
  return value as unknown as NodeSessionsResponse;
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
