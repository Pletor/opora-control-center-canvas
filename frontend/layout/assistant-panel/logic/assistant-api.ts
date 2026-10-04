import { api } from "@/shared/types/logic/types";
import type { SessionState } from "./assistant-events";

export type AssistantModel = "opus" | "sonnet" | "fable";
export const MODELS: AssistantModel[] = ["opus", "sonnet", "fable"];

export type AssistantStatus = { available: boolean; claudePath: string | null; version: string | null; running: number; limit: number };

export type AssistantSession = {
  id: string;
  projectId: string;
  workspace: string;
  title: string;
  model: string;
  claudeSessionId: string | null;
  createdAt: string;
  updatedAt: string;
  state: SessionState;
  nodeId: string | null;
  lastSeq: number;
};

/** Rozsah práce (docs/asistent.md §6.1): celý obraz, nebo jen vybrané uzly do hloubky. */
export type AssistantScope = "board" | "selection";
export const SCOPES: AssistantScope[] = ["board", "selection"];

/** Na co se uživatel dívá (dodá App); panel k tomu přidá rozsah z preferencí. */
export type ViewContext = {
  projectId: string;
  workspace: string;
  layerId: string | null;
  selectedNodeIds: string[];
  environment: "project" | "editor" | "live";
};

/** Co uživatel právě vidí a v jakém rozsahu; backend to vloží před text zprávy jako údaj, ne pokyn. */
export type AssistantContext = ViewContext & { scope: AssistantScope };

const base = "/api/assistant";
const sessionUrl = (id: string) => `${base}/sessions/${encodeURIComponent(id)}`;

export const fetchStatus = () => api<AssistantStatus>(`${base}/status`);

export const fetchSessions = (project: string) =>
  api<{ sessions: AssistantSession[] }>(`${base}/sessions?project=${encodeURIComponent(project)}`).then((r) => r.sessions);

export const createSession = (body: { project: string; workspace?: string; title?: string; model?: AssistantModel }) =>
  api<{ session: AssistantSession }>(`${base}/sessions`, body).then((r) => r.session);

export const sendMessage = (id: string, text: string, context: AssistantContext) =>
  api<unknown>(`${sessionUrl(id)}/messages`, { text, context });

export const stopSession = (id: string) => api<unknown>(`${sessionUrl(id)}/stop`, {});

export const renameSession = (id: string, title: string) =>
  api<{ session: AssistantSession }>(`${sessionUrl(id)}/title`, { title }).then((r) => r.session);

export const closeSession = (id: string) => api<unknown>(`${sessionUrl(id)}/close`, {});

export const fetchTranscript = (id: string) =>
  api<{ messages: { role: "user" | "assistant"; text: string }[] }>(`${sessionUrl(id)}/transcript`).then((r) => r.messages);

/** Rozhodnutí člověka o zápisu na plátno (§5.1); poznámka jde asistentovi jako důvod zamítnutí. */
export const decideApproval = (approvalId: string, decision: "allow" | "deny", note?: string) =>
  api<{ approvalId: string; decision: string; session: AssistantSession }>(
    `${base}/approvals/${encodeURIComponent(approvalId)}`,
    note ? { decision, note } : { decision },
  );

export const eventsUrl = (id: string, after: number) => `${sessionUrl(id)}/events?after=${after}`;
