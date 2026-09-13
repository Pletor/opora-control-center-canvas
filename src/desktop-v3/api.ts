// Klient pro sdílené API Desktop v3. Fetch přes existující api() z ../types.
import { api } from "@/types";
import type {
  DesktopState,
  StateResponse,
  PacketPreviewResponse,
  PacketSnapshotResponse,
  HandoffRun,
  PlanningRun,
} from "@/desktop-v3/types";

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

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export type SnapshotReadbackExpectation = {
  id: string;
  digest: string;
  project: string;
  workspace: string;
  nodeId: string;
};

/** Fail-closed kontrola readbacku snímku: vrací stejný objekt, jinak vyhodí chybu. */
export function assertSnapshotReadback(value: unknown, expected: SnapshotReadbackExpectation): PacketSnapshotResponse {
  if (!isRecord(value) || !isRecord(value.packet)) throw new Error("Načtený snímek má neplatný tvar.");
  if (value.id !== expected.id || value.digest !== expected.digest)
    throw new Error("Načtený snímek neodpovídá vytvořenému snímku a digestu.");
  const scope = value.packet.scope;
  if (
    !isRecord(scope) ||
    scope.project !== expected.project ||
    scope.workspace !== expected.workspace ||
    scope.nodeId !== expected.nodeId
  )
    throw new Error("Načtený snímek nemá rozsah vybraného projektu, prostředí a uzlu.");
  return value as PacketSnapshotResponse;
}

export async function fetchSnapshot(expected: SnapshotReadbackExpectation): Promise<PacketSnapshotResponse> {
  const { id, project, workspace } = expected;
  const value = await api<unknown>(
    `/api/desktop-v3/packet/snapshots/${encodeURIComponent(id)}?${query({ project, workspace })}`,
  );
  return assertSnapshotReadback(value, expected);
}

export type ExternalTaskExport = {
  snapshotId: string; digest: string; project: string; workspace: string; nodeId: string;
  path: string; sha256: string; content: string;
};

export async function exportExternalTask(expected: SnapshotReadbackExpectation): Promise<ExternalTaskExport> {
  const { id, digest, project, workspace, nodeId } = expected;
  const endpoint = `/api/desktop-v3/packet/snapshots/${encodeURIComponent(id)}/external-export`;
  const payload = { digest, project, workspace, nodeId };
  const written = await api<ExternalTaskExport>(endpoint, payload);
  const read = await api<ExternalTaskExport>(`${endpoint}?${query(payload)}`);
  for (const value of [written, read]) {
    if (value.snapshotId !== id || value.digest !== digest || value.project !== project ||
        value.workspace !== workspace || value.nodeId !== nodeId ||
        value.path !== `docs/opora-control-center/tasks/${nodeId}.md` ||
        typeof value.content !== "string" || !/^[a-f0-9]{64}$/.test(value.sha256)) {
      throw new Error("Export nemá očekávanou identitu, cestu nebo rozsah.");
    }
  }
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(read.content));
  const actual = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, "0")).join("");
  if (written.sha256 !== read.sha256 || actual !== read.sha256 || written.content !== read.content) {
    throw new Error("Zpětné čtení souboru zadání neodpovídá zápisu.");
  }
  return read;
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

/** Přesný tvar GET /api/task-handoffs/{id}/export (backend/task_handoffs.py export()). */
export type HandoffExport = {
  id: string;
  digest: string;
  scope: { project: string; workspace: string; node: string | null };
  task: string;
  allowedFiles: string[];
  readableNodeIds: string[];
  context: unknown;
  provider: string;
  model: string;
  budgetSeconds: number;
};

export type HandoffExportExpectation = {
  id: string;
  digest: string;
  project: string;
  workspace: string;
  node: string | null;
};

/** Fail-closed kontrola exportu: přesný běh (id + digest) a jeho rozsah. Vrací stejný objekt beze
 * změny; cokoli jiného (chybějící/poškozený scope, cizí projekt/prostředí/uzel) vyhodí chybu. */
export function assertHandoffExport(value: unknown, expected: HandoffExportExpectation): HandoffExport {
  if (!isRecord(value) || typeof value.task !== "string" || !("context" in value))
    throw new Error("Export běhu má neplatný tvar.");
  if (value.id !== expected.id || value.digest !== expected.digest)
    throw new Error("Export neodpovídá vybranému běhu.");
  const scope = value.scope;
  if (
    !isRecord(scope) ||
    typeof scope.project !== "string" ||
    typeof scope.workspace !== "string" ||
    !(typeof scope.node === "string" || scope.node === null)
  )
    throw new Error("Export nemá platný rozsah projektu, prostředí a uzlu.");
  if (scope.project !== expected.project || scope.workspace !== expected.workspace || scope.node !== expected.node)
    throw new Error("Export patří jinému projektu, prostředí nebo uzlu.");
  return value as HandoffExport;
}

export async function exportHandoff(expected: HandoffExportExpectation): Promise<HandoffExport> {
  const value = await api<unknown>(`/api/task-handoffs/${encodeURIComponent(expected.id)}/export`);
  return assertHandoffExport(value, expected);
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
