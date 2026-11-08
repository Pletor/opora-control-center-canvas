import { api } from "@/shared/types/logic/types";
import type { ResearchDetail, ResearchEdgeDetail, ResearchGraph, ResearchScope } from "./research-types";
export const researchUrls = {
  overview: (scope: ResearchScope, archived: boolean) => `/api/research?${new URLSearchParams({ ...scope, archived: archived ? "1" : "0" })}`,
  edge: (scope: ResearchScope, id: string, revision?: number) => `/api/research/edges/${encodeURIComponent(id)}?${new URLSearchParams({ ...scope, ...(revision === undefined ? {} : { revision: String(revision) }) })}`,
  detail: (scope: ResearchScope, id: string, revision?: number) => `/api/research/cards/${encodeURIComponent(id)}?${new URLSearchParams({ ...scope, ...(revision === undefined ? {} : { revision: String(revision) }) })}`,
};
export const loadResearch = (scope: ResearchScope, archived: boolean) => api<ResearchGraph>(researchUrls.overview(scope, archived));
export const loadResearchDetail = (scope: ResearchScope, id: string, revision?: number) => api<ResearchDetail>(researchUrls.detail(scope, id, revision));
export const archiveResearch = (scope: ResearchScope, entity: "card" | "edge", id: string, expectedRevision: number, archived: boolean) =>
  api("/api/research", { ...scope, key: crypto.randomUUID(), operations: [{ op: "archive", entity, id, expectedRevision, archived }] });
/** A response belongs to the exact request generation and scope, including detail revision. */
export function requestGate() {
  let generation = 0;
  return { begin: () => ++generation, accepts: (ticket: number) => ticket === generation, invalidate: () => { ++generation; } };
}

export const loadResearchEdge = (scope: ResearchScope, id: string, revision?: number) => api<ResearchEdgeDetail>(researchUrls.edge(scope, id, revision));

export type ResearchEvents = { project: string; workspace: string; nextCursor: number; hasMore: boolean;
  events: { cursor: number; type: string; cards: { id: string; revision: number }[]; edges: { id: string; revision: number }[] }[] };
export const loadResearchEvents = (scope: ResearchScope, after: number) =>
  api<ResearchEvents>(`/api/research/events?${new URLSearchParams({ ...scope, after: String(after) })}`);
