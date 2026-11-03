// Plátno záměru stránky nad API engine toků (`backend/api/flow/README.md`, kontrakt
// `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §3 a §5). Workflow `page_intent` patří stránce přes
// `owner_ref = opora:page:<nodeId>`; neexistuje-li, založí ho až první uložený draft. Schválit a zamítnout smí jen
// člověk: `api` u zápisu sám obstará relační doklad UI (cookie `opora_ui`), stejně jako u ostatních akcí `require_human`.
import { api } from "@/shared/types/logic/types";
import type { FlowGraph, FlowVersion, FlowWorkflow, NodeTypeSpec } from "@/shared/flow-editor/logic/flow-types";
import { saveDraft } from "@/project/heart-canvas/logic/heart-api";

const BASE = "/api/flow";
export const INTENT_KIND = "page_intent";
export const ownerRef = (page: string) => `opora:page:${page}`;
const list = <T>(raw: unknown, key: string): T[] => {
  const value = raw && typeof raw === "object" ? (raw as Record<string, unknown>)[key] : null;
  return Array.isArray(value) ? value as T[] : [];
};

export const intentUrls = {
  workflows: (project: string, page: string) => `${BASE}/workflows?${new URLSearchParams({ project, kind: INTENT_KIND, owner_ref: ownerRef(page) })}`,
  create: () => `${BASE}/workflows`,
  nodeTypes: () => `${BASE}/node-types?kind=${INTENT_KIND}`,
  approve: (version: string) => `${BASE}/versions/${encodeURIComponent(version)}/approve`,
  reject: (version: string) => `${BASE}/versions/${encodeURIComponent(version)}/reject`,
};

/** Workflow záměru této stránky; plátno pozná svůj druh jen z `kind` workflow. */
export function pickIntentWorkflow(workflows: readonly FlowWorkflow[], page: string): FlowWorkflow | null {
  return workflows.find((item) => item.kind === INTENT_KIND && item.owner_ref === ownerRef(page)) ?? null;
}

export const loadIntentWorkflow = (project: string, page: string) =>
  api<unknown>(intentUrls.workflows(project, page)).then((raw) => pickIntentWorkflow(list<FlowWorkflow>(raw, "workflows"), page));
export const loadIntentTypes = () => api<unknown>(intentUrls.nodeTypes()).then((raw) => list<NodeTypeSpec>(raw, "node_types"));

/** Uloží graf jako nový draft; bez workflow ho nejdřív založí (vlastník = stránka). */
export async function saveIntentDraft(workflow: FlowWorkflow | null, project: string, page: string, graph: FlowGraph, parent: string | null): Promise<FlowVersion> {
  const target = workflow ?? await api<FlowWorkflow>(intentUrls.create(), { kind: INTENT_KIND, name: `Záměr stránky ${page}`, project_id: project, owner_ref: ownerRef(page) });
  return saveDraft(target.id, graph, parent);
}
export const approveVersion = (version: string) => api<FlowVersion>(intentUrls.approve(version), {});
export const rejectVersion = (version: string, reason: string) => api<FlowVersion>(intentUrls.reject(version), { reason: reason.trim() });
