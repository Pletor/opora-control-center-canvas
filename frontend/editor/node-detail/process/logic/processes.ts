import { api } from "@/shared/types/logic/types";

/** Kontrakt procesu: shared/process.schema.json. Stavy: návrh → proces → hotovo → oprava. */
export type ProcessState = "draft" | "running" | "done" | "repair";
export type StepState = "pending" | "running" | "done" | "failed";
export type Actor = { kind: "human" | "agent" | "system"; name: string };

export type Evidence = { summary: string; at: string; by: Actor; reportId?: string | null; outputs?: string[] };
export type Step = { id: string; title: string; state: StepState; evidence: Evidence | null };
export type Output = { kind: "json" | "db" | "md" | "file"; ref: string; digest?: string | null };
export type Failure = { reason: string; stepId: string | null; at: string; reportedBy: Actor; fix?: string | null };
export type HistoryEntry = { from: ProcessState | null; to: ProcessState; at: string; by: Actor; note: string };

export type Process = {
  id: string;
  projectId: string;
  nodeId: string | null;
  sectorId: string | null;
  title: string;
  state: ProcessState;
  createdAt: string;
  updatedAt: string;
  revision: number;
  owner: Actor;
  inputs: { nodeText: string | null; spec: string | null; packet: string | null; worktree: string | null; references: string[] };
  steps: Step[];
  outputs: Output[];
  failure: Failure | null;
  history: HistoryEntry[];
};

export type Allowed = Record<"human" | "agent" | "system", ProcessState[]>;
export type ProcessWithAllowed = Process & { allowed: Allowed };
export type Report = {
  id: string;
  kind: "progress" | "step_done" | "step_failed" | "question" | "result";
  at: string;
  by: Actor;
  summary: string;
  stepId: string | null;
  error: string | null;
  stale: boolean;
};

export const STATE_LABEL: Record<ProcessState, string> = { draft: "Návrh", running: "Proces", done: "Hotovo", repair: "Oprava" };
export const STEP_LABEL: Record<StepState, string> = { pending: "čeká", running: "běží", done: "hotovo", failed: "selhal" };
export const HUMAN: Actor = { kind: "human", name: "uživatel" };

export function listProcesses(project: string, nodeId?: string, state?: ProcessState): Promise<ProcessWithAllowed[]> {
  const params = new URLSearchParams({ project });
  if (nodeId) params.set("nodeId", nodeId);
  if (state) params.set("state", state);
  return api<{ processes: ProcessWithAllowed[] }>("/api/processes?" + params.toString()).then((r) => r.processes);
}

export function readProcess(project: string, id: string): Promise<{ process: Process; reports: Report[]; allowed: Allowed }> {
  return api("/api/processes/" + encodeURIComponent(id) + "?project=" + encodeURIComponent(project));
}

export function createProcess(project: string, nodeId: string, title: string, steps: string[], worktree: string | null): Promise<Process> {
  return api<{ process: Process }>("/api/processes", { project, nodeId, title, steps, inputs: { worktree }, by: HUMAN, owner: HUMAN }).then((r) => r.process);
}

export function transitionProcess(project: string, process: Process, to: ProcessState, note = "", extra: { fix?: string; failure?: Failure | { reason: string; stepId: string | null; reportedBy: Actor } } = {}): Promise<Process> {
  return api<{ process: Process }>("/api/processes/" + encodeURIComponent(process.id) + "/transition", {
    project,
    revision: process.revision,
    to,
    note,
    by: HUMAN,
    ...extra,
  }).then((r) => r.process);
}

export function markStep(project: string, process: Process, stepId: string, state: StepState, summary?: string): Promise<Process> {
  const evidence = summary ? { summary, at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"), by: HUMAN, reportId: null, outputs: [] } : undefined;
  return api<{ process: Process }>("/api/processes/" + encodeURIComponent(process.id) + "/steps/" + encodeURIComponent(stepId), {
    project,
    revision: process.revision,
    state,
    evidence,
  }).then((r) => r.process);
}
