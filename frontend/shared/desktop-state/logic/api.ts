// Klient pro sdílené API Desktop v3. Fetch přes existující api() z ../types.
import { api } from "@/shared/types/logic/types";
import type {
  AgentWorkspaceSummaries,
  DesktopState,
  NodeBrief,
  StateResponse,
  PacketPreviewResponse,
  PacketSnapshotResponse,
  PipelineLibrary,
  SyncReport,
} from "@/shared/desktop-state/logic/types";

/** Knihovna předloh pipeline pro blok Akce; verzovaná v library/, jen ke čtení. */
export function fetchPipelines(): Promise<PipelineLibrary> {
  return api<PipelineLibrary>("/api/desktop-v3/pipelines");
}

/**
 * Balíček pro model: jeden JSON s celou kartou (cíl, hranice, kontext, harness, bloky, graf, smyčka).
 * Jen ke čtení a jen na vyžádání člověka; nic se tím modelu neodesílá.
 */
export function fetchNodeBrief(project: string, workspace: string, nodeId: string): Promise<NodeBrief> {
  return api<NodeBrief>(`/api/desktop-v3/node-brief?${query({ project, workspace, nodeId })}`);
}

/**
 * Levný souhrn paměti všech karet jedním dotazem (vyplněná pole, autor, čas), bez komunikace a
 * ověření. Stačí na hlavičky sbalených kapitol; plný stav karty nese jen `fetchNodeBrief`.
 */
export function fetchAgentWorkspaceSummaries(project: string, workspace: string): Promise<AgentWorkspaceSummaries> {
  return api<AgentWorkspaceSummaries>(`/api/desktop-v3/agent-workspace-summaries?${query({ project, workspace })}`);
}

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

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/**
 * Echo a verdikt Oracle nad projektem (`GET /api/sync-report`). Jen čtení: říká, co nesedí mezi
 * zadáním, kódem a gitem, a jestli rozsah smí do mainu. Nic nespouští a nic neukládá.
 */
export function fetchSyncReport(project: string, workspace: string): Promise<SyncReport> {
  return api<SyncReport>(`/api/sync-report?${query({ project, workspace })}`);
}

/**
 * Commit zadání v OporaHubu. Obsah si backend vezme ze svého stavu, tělo nese jen rozsah,
 * popisek a autora; agent tudy zapsat nesmí, hlídá si to úložiště samo.
 */
export function commitSpec(project: string, workspace: string, scope: string, subject: string) {
  return api<{ id: string; specRevision: number }>("/api/opora-commit", {
    project, workspace, scope, subject, by: { kind: "human", name: "Člověk" },
  });
}

