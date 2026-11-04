// Knihovna pláten toku nad API (`backend/api/flow/library_routes.py`, kontrakt
// `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §3): složky a plátna části Člověk / Agent, detail plátna s verzemi
// a rodokmenem, převzetí do projektu, uložení vylepšení a povýšení. Verze a graf jdou přes engine toků
// (`/api/flow/workflows/{id}/versions`); plátno toku se aktivuje bez schválení (draft → candidate → active).
import { api } from "@/shared/types/logic/types";
import type { FlowGraph, FlowVersion, NodeTypeSpec, PortSpec } from "@/shared/flow-editor/logic/flow-types";

export type LibraryOwner = "human" | "agent";
export type LibraryFlowSummary = { id: string; slug: string | null; title: string; description: string | null; ownerRef: string; projectId: string | null;
  activeVersionId: string | null; activeN: number | null; derivedCount: number };
export type LibraryFolder = { id: string; owner: LibraryOwner; slug: string; title: string; description: string; order: number; flows: LibraryFlowSummary[] };
export type DerivedFrom = { workflowId: string; versionId: string };
export type LibraryFlowDetail = LibraryFlowSummary & {
  versions: (FlowVersion & { derived_from?: DerivedFrom | null })[]; derivedFrom: DerivedFrom | null;
  derived: { workflowId: string; name: string; projectId: string | null; ownerRef: string }[]; projects: string[];
};

const LIB = "/api/library", FLOW = "/api/flow";
const id = encodeURIComponent;
export const KIND = "library_flow";
export const libraryUrls = {
  list: (owner: LibraryOwner) => `${LIB}?${new URLSearchParams({ owner })}`,
  folders: () => `${LIB}/folders`,
  flows: () => `${LIB}/flows`,
  flow: (flow: string) => `${LIB}/flows/${id(flow)}`,
  adopt: (flow: string) => `${LIB}/flows/${id(flow)}/adopt`,
  contribute: (flow: string) => `${LIB}/flows/${id(flow)}/contribute`,
  promote: (flow: string) => `${LIB}/flows/${id(flow)}/promote`,
  types: () => `${FLOW}/node-types?kind=${KIND}`,
  nodePorts: () => `${FLOW}/node-ports`,
  check: () => `${FLOW}/graph-check`,
  versions: (flow: string) => `${FLOW}/workflows/${id(flow)}/versions`,
  candidate: (version: string) => `${FLOW}/versions/${id(version)}/candidate`,
  activate: (version: string) => `${FLOW}/versions/${id(version)}/activate`,
  rollback: (flow: string) => `${FLOW}/workflows/${id(flow)}/rollback`,
  projectFlows: (project: string) => `${FLOW}/workflows?${new URLSearchParams({ project, kind: KIND })}`,
};

const field = <T>(raw: unknown, key: string, fallback: T): T => {
  const value = raw && typeof raw === "object" ? (raw as Record<string, unknown>)[key] : undefined;
  return value === undefined || value === null ? fallback : value as T;
};

export const loadLibrary = (owner: LibraryOwner) => api<unknown>(libraryUrls.list(owner)).then((raw) => field<LibraryFolder[]>(raw, "folders", []));
export const createFolder = (owner: LibraryOwner, slug: string, title: string, description = "") => api<LibraryFolder>(libraryUrls.folders(), { owner, slug, title, description });
export const createFlow = (folder: string, slug: string, title: string, description?: string) =>
  api<LibraryFlowDetail>(libraryUrls.flows(), { folder, slug, title, ...(description ? { description } : {}) });
export const loadFlow = (flow: string) => api<LibraryFlowDetail>(libraryUrls.flow(flow));
export const loadLibraryTypes = () => api<unknown>(libraryUrls.types()).then((raw) => field<NodeTypeSpec[]>(raw, "node_types", []));
export const adoptFlow = (flow: string, project: string, nodeId?: string) => api<LibraryFlowDetail>(libraryUrls.adopt(flow), { project, ...(nodeId ? { nodeId } : {}) });
export const contributeFlow = (flow: string, folder: string, slug: string, title: string) => api<LibraryFlowDetail>(libraryUrls.contribute(flow), { folder, slug, title });
export const promoteFlow = (flow: string) => api<LibraryFlowDetail>(libraryUrls.promote(flow), {});
export const saveFlowDraft = (flow: string, graph: FlowGraph, parent: string | null) => api<FlowVersion>(libraryUrls.versions(flow), { graph, parent_version_id: parent });
/** Aktivace bez schválení: draft se stane kandidátem a hned aktivní verzí; vyřazená verze (návrat) se aktivuje rovnou. */
export async function activateVersion(version: FlowVersion): Promise<FlowVersion> {
  if (version.status === "draft") await api<FlowVersion>(libraryUrls.candidate(version.id), {});
  return api<FlowVersion>(libraryUrls.activate(version.id), {});
}
export const rollbackFlow = (flow: string) => api<FlowVersion>(libraryUrls.rollback(flow), {});
export const nodePorts = (type: string, params: Record<string, unknown>, onError?: string) =>
  api<unknown>(libraryUrls.nodePorts(), { kind: KIND, type, params, ...(onError ? { onError } : {}) }).then((raw) => field<PortSpec[]>(raw, "ports", []));
export const checkGraph = (graph: FlowGraph) => api<unknown>(libraryUrls.check(), { kind: KIND, graph }).then((raw) => field<string[]>(raw, "errors", []));

/** Kde plátno leží podle vlastníka: knihovna člověka, knihovna agenta, nebo kopie v projektu. */
export const placeOf = (ownerRef: string): "human" | "agent" | "project" =>
  ownerRef.startsWith("opora:library:human:") ? "human" : ownerRef.startsWith("opora:library:agent:") ? "agent" : "project";

/** Slug z titulku: malá písmena bez diakritiky, číslice a pomlčky (pravidlo backendu `a-z0-9-`, nejvýš 64 znaků). */
export function slugOf(title: string): string {
  return title.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64) || "platno";
}
