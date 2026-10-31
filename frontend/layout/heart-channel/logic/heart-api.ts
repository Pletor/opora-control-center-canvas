import { api } from "@/shared/types/logic/types";
import type { ActivityEntry } from "@/editor/canvas/activity-log/logic/activity-log";

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

/** Vstup, který dávku probudil (tvar `inputs` deníku dávek; `type` určuje ostatní pole). */
export type HeartInput = { type: string; text?: string; kind?: string; pr?: number | string | null; [key: string]: unknown };

/** Běžící dávka (`current` stavu srdce); bez dávky `null`. */
export type HeartCurrent = { startedAt: string; inputs: HeartInput[] };

export type HeartBatch = {
  /** Začátek dávky (ISO UTC). */
  at: string;
  durationMs?: number;
  inputs?: HeartInput[];
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
  current?: HeartCurrent | null;
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

/** Zápisy srdce v záznamu činnosti za rozsah (`query` z `heartStepsQuery`), nejnovější první. */
export const fetchHeartSteps = (query: string) => api<{ entries: ActivityEntry[] }>(query).then((r) => r.entries);

/** Připravený text pro srdce z jiné části aplikace (Kancelář, živý panel domény) a prostor, kterého se týká. */
export type HeartRequest = { workspace: string; text: string };

export const sendHeartMessage = (project: string, workspace: string, text: string) =>
  api<{ queued: boolean; pending: number }>("/api/brain/heart/messages", { project, workspace, text });
