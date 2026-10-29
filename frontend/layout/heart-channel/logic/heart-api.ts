import { api } from "@/shared/types/logic/types";

/** Síťová volání kanálu Srdce (docs/brain-heart-channel.md §2). Všechny routy existují v backendu. */

export type Escalation = { ticketId: string; text: string; createdAt: string; taskId?: string | null };

export type QueueStatus = "ready" | "assigned" | "done" | "failed" | "cancelled";

export type QueueTask = {
  taskId: string;
  title: string;
  status: QueueStatus;
  sessionId: string | null;
  nodeId: string | null;
  createdBy: string;
  updatedAt: string;
  order: number;
  body: { do: string; doneWhen?: string[] };
};

export type HeartBatch = {
  at: string;
  status: string;
  costUsd: number | null;
  summary: string | null;
  error?: string;
};

export type HeartStatus = {
  enabled: boolean;
  running: boolean;
  pending: number;
  batches: HeartBatch[];
  sleeping: boolean;
  sleepingUntil: string | null;
  nextAllowedAt: string | null;
  error: string | null;
};

const scope = (project: string, workspace: string) =>
  `project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}`;

export const fetchGateSetting = (project: string) =>
  api<{ enabled: boolean }>(`/api/brain/gate-setting?project=${encodeURIComponent(project)}`).then((r) => r.enabled === true);

export const enableGate = (project: string) =>
  api<{ enabled: boolean }>("/api/brain/gate-setting", { project, enabled: true }).then((r) => r.enabled === true);

export const fetchEscalations = (project: string, workspace: string) =>
  api<{ escalations: Escalation[] }>(`/api/brain/heart/escalations?${scope(project, workspace)}`).then((r) => r.escalations);

/** Odpověď člověka na eskalaci; backend jí srdce hned probudí. */
export const answerEscalation = (project: string, ticketId: string, text: string) =>
  api<unknown>(`/api/gate/tickets/${encodeURIComponent(ticketId)}/answer?project=${encodeURIComponent(project)}`, {
    answer: { text },
  });

export const fetchQueue = (project: string, workspace: string) =>
  api<{ tasks: QueueTask[] }>(`/api/brain/tasks?${scope(project, workspace)}`).then((r) => r.tasks);

export const fetchHeartStatus = (project: string) =>
  api<HeartStatus>(`/api/brain/heart/status?project=${encodeURIComponent(project)}`);

/** Připravený text pro srdce z jiné části aplikace (Kancelář, živý panel domény) a prostor, kterého se týká. */
export type HeartRequest = { workspace: string; text: string };

export const sendHeartMessage = (project: string, workspace: string, text: string) =>
  api<{ queued: boolean; pending: number }>("/api/brain/heart/messages", { project, workspace, text });
