export type AgentSourceHealth = {
  available: boolean;
  status?: string;
  error?: string;
  lanes?: string[];
};

export type AgentRunStatus = {
  reported: string;
  liveness: string;
  note?: string | null;
};

export type AgentRunPreviewBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; name?: string; input?: string }
  | { type: "tool_result"; content?: string }
  | { type: string };

export type AgentRunPreviewEvent = {
  kind: string;
  content?: AgentRunPreviewBlock[];
  subtype?: string;
  summary?: string;
};

export type AgentRunCost = {
  todayUsd: number | null;
  limitUsd: number | null;
  reliable: boolean;
  note?: string | null;
} | null;

export type AgentRunSummary = {
  sourceId: string;
  runId: string;
  sourceRef?: string;
  sessionId?: string | null;
  modelAlias?: string | null;
  stateOrigin: string;
  sourceTimestamp: string | null;
  lastEventSeq: number | null;
  status: AgentRunStatus;
  preview: AgentRunPreviewEvent[];
  cost: AgentRunCost;
  missing: string[];
};

export type AgentBrainLevels = {
  promptSpec: string | "unavailable";
  contextSnapshot: string | "unavailable";
  toolAction: AgentRunPreviewEvent | null | "unavailable";
  verifierArtifact: string | "unavailable";
  iterations: string | "unavailable";
  maxIterations: string | "unavailable";
  budget: string | "unavailable";
  noProgressSignal: string | "unavailable";
  doneReason: string | null;
};

export type AgentRunDetail = AgentRunSummary & {
  brain?: AgentBrainLevels;
  available?: boolean;
  error?: string;
};

export type AgentRunsPage = {
  items: AgentRunSummary[];
  nextCursor: number | null;
  total: number;
};

export type AgentBindingCandidate = { sourceId: string; runId: string };

export type AgentBinding = {
  bindingId: string;
  sourceId: string;
  runId: string;
  sessionId: string | null;
  layer: string;
  createdAt: string;
};

export type AgentBindingList = { revision: number; items: AgentBinding[] };

export type AgentActivityEntry = {
  entryId: string;
  sourceId: string;
  runId: string;
  sourceEventId: string;
  sourceTimestamp: string | null;
  ingestTimestamp: string;
  kind: string;
  summary: string;
};

/** Kontrakt pro rodičovskou integraci: uzel v Canvasu zavolá tento callback, aby otevřel
 * detail aktivity daného uzlu/sektoru v AgentsWorkspace (bez vlastní navigace routeru). */
export type OpenNodeActivity = (nodeId: string) => void;
