// Klient pro sdílené API Desktop v3. Fetch přes existující api() z ../types.
import { api } from "../types";
import type {
  DesktopState,
  StateResponse,
  PacketPreviewResponse,
  PacketSnapshotResponse,
  HandoffRun,
  PlanningRun,
} from "./types";

const query = (params: Record<string, string>): string =>
  Object.entries(params)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");

export function fetchState(project: string, workspace: string): Promise<StateResponse> {
  return api<StateResponse>(`/api/desktop-v3/state?${query({ project, workspace })}`);
}

export function saveState(
  project: string,
  workspace: string,
  expectedRevision: number,
  state: DesktopState,
): Promise<StateResponse> {
  return api<StateResponse>("/api/desktop-v3/state", { project, workspace, expectedRevision, state });
}

export type PacketPreviewInput = {
  project: string;
  workspace: string;
  nodeId: string;
  path: string;
  sessionId: string;
  references: string[];
  note: string;
};

export function previewPacket(input: PacketPreviewInput): Promise<PacketPreviewResponse> {
  return api<PacketPreviewResponse>("/api/desktop-v3/packet/preview", { ...input });
}

export type PacketSnapshotInput = PacketPreviewInput & { digest: string };

export function snapshotPacket(input: PacketSnapshotInput): Promise<PacketSnapshotResponse> {
  return api<PacketSnapshotResponse>("/api/desktop-v3/packet/snapshot", { ...input });
}

export function fetchSnapshot(
  id: string,
  project: string,
  workspace: string,
): Promise<PacketSnapshotResponse> {
  return api<PacketSnapshotResponse>(
    `/api/desktop-v3/packet/snapshots/${encodeURIComponent(id)}?${query({ project, workspace })}`,
  );
}

export function prepareSnapshotRun(
  id: string,
  project: string,
  workspace: string,
  task: string,
): Promise<HandoffRun> {
  return api<HandoffRun>(`/api/desktop-v3/packet/snapshots/${encodeURIComponent(id)}/prepare`, {
    project,
    workspace,
    task,
  });
}

export function fetchHandoff(id: string): Promise<HandoffRun> {
  return api<HandoffRun>(`/api/task-handoffs/${encodeURIComponent(id)}`);
}

export function startHandoff(id: string, digest: string): Promise<HandoffRun> {
  return api<HandoffRun>(`/api/task-handoffs/${encodeURIComponent(id)}/start`, { digest, confirmed: true });
}

export function stopHandoff(id: string): Promise<HandoffRun> {
  return api<HandoffRun>(`/api/task-handoffs/${encodeURIComponent(id)}/stop`, { confirmed: true });
}

export function exportHandoff(id: string): Promise<{ id: string; digest: string; task: string; context: unknown }> {
  return api<{ id: string; digest: string; task: string; context: unknown }>(
    `/api/task-handoffs/${encodeURIComponent(id)}/export`,
  );
}

export function fetchHandoffRuns(project: string, workspace: string): Promise<{ runs: HandoffRun[] }> {
  return api<{ runs: HandoffRun[] }>(`/api/task-handoffs?${query({ project, workspace })}`);
}

export function fetchPlanningRuns(project: string): Promise<{ runs: PlanningRun[]; active: PlanningRun | null }> {
  return api<{ runs: PlanningRun[]; active: PlanningRun | null }>(`/api/llm/runs?${query({ project })}`);
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export const ACTIVE_HANDOFF_STATUSES = new Set<HandoffRun["status"]>([
  "starting",
  "running",
  "stopping",
  "verifying",
]);
