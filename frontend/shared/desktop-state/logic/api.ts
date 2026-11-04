// Klient pro sdílené API Desktop v3. Fetch přes existující api() z ../types.
import { api, type NodeSpec, type SpecFields } from "@/shared/types/logic/types";
import type {
  AgentWorkspaceSummaries,
  DesktopState,
  NodeBrief,
  NodeWorkflowState,
  StateResponse,
  PipelineLibrary,
  SyncReport,
} from "@/shared/desktop-state/logic/types";
import type { NodeWriteResponse } from "@/shared/desktop-state/logic/slim-writes";

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

/** Štíhlý zápis jedné karty (oprava 8): tělo i odpověď nesou jen `nodes[nodeId]`, ne celý stav. */
export function saveNode(
  project: string,
  workspace: string,
  expectedRevision: number,
  nodeId: string,
  node: NodeWorkflowState | null,
): Promise<NodeWriteResponse> {
  return api<NodeWriteResponse>("/api/desktop-v3/node", { project, workspace, expectedRevision, nodeId, node });
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
 * Uloží zadání karty (cíl, co není součástí, podmínky dokončení) přes `POST /api/node-spec` —
 * totéž API, kterým ukládá záložka Zadání. `expectedRevision` hlídá souběh; nová karta má 0.
 */
export function saveNodeSpec(project: string, workspace: string, node: string, expectedRevision: number, fields: SpecFields): Promise<NodeSpec> {
  return api<NodeSpec>("/api/node-spec", { project, workspace, node, expected_revision: expectedRevision, fields });
}
