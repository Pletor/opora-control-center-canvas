import type { ResearchCard, ResearchHeader } from "./research-types";
export type CanonicalRef = { projectId: string; workspaceId: string; id: string; revision: number };
export type KnowledgeRecord = { canonicalRef: CanonicalRef; card: ResearchHeader;
 contexts: { relation: "local" | "parent" | "shared"; scopeNodeId: string | null }[];
 provenance: { projectId: string; workspaceId: string; sources: Partial<ResearchCard["sources"][number]>[]; by: string };
 verification: ResearchCard["verification"] };
export const knowledgeIdentity = (ref: CanonicalRef) => JSON.stringify([ref.projectId, ref.workspaceId, ref.id, ref.revision]);
export type SolutionVerification = { status: "unknown" | "unproven" | "reported_evidence"; reason?: string;
 verified?: boolean; independent?: false; level?: "reported_evidence"; source?: string; acceptedRevision?: string;
 currentAcceptedRevision?: string; assignmentDigest?: string; headSha?: string; executionId?: string; receiptId?: string };
export type KnowledgeSolution = { solutionRef: { projectId: string; nodeId: string }; title: string; purpose: string;
 snapshot: { workspaceId: string; graphDigest: string }; verification: SolutionVerification; evidence: KnowledgeRecord[];
 match?: { score: number; lexical: number; semantic: number | null; graph: number };
 facts?: { specification: { acceptedRevision: string; revision: number; fields: Record<string, unknown>; fieldsTruncated?: string[] } | null;
 inputs: { nodeId: string; name: string; sourceNodeId?: string; sourceName?: string; relation: string; requirement?: unknown }[]; inputsTruncated: boolean; sources: CanonicalRef[] };
 snapshots?: { workspaceId: string; graphDigest: string; verification: SolutionVerification }[] };
export type SearchRetrieval = { requested: string; used: string; candidates: number; candidatesRanked: number; candidateLimit: number;
 truncated: boolean; candidatePassagesTruncated: boolean; semantic: {status: string; model: string; detail?: string; maxPassageTokens?: number} };
export type SolutionComparison = { basis: string; commonSources: CanonicalRef[];
 differences: {field: string; values: {solutionRef: {projectId: string; nodeId: string}; workspaceId: string; value: unknown}[]}[] };
export function solutionVerificationLabel(value: SolutionVerification) {
 return value.status === "reported_evidence" && value.verified === true && value.independent === false
  && value.level === "reported_evidence" ? "Doloženo Kanceláří" : "Nedoloženo";
}
export function solutionVerificationDetail(value: SolutionVerification) {
 return solutionVerificationLabel(value) === "Doloženo Kanceláří"
  ? `Kladný i záporný integrační test; zadání ${value.acceptedRevision}, commit ${value.headSha}, běh ${value.executionId}, doklad ${value.receiptId}. Zdroj: ${value.source}. Nejde o nezávislé spuštění testů.`
  : value.reason ?? "Funkční důkaz konkrétní revize není doložen.";
}
export function sourceRoute(ref: CanonicalRef) {
 return "/?" + new URLSearchParams({screen: "canvas", mode: "research", project: ref.projectId, workspace: ref.workspaceId, researchSource: ref.id, researchRevision: String(ref.revision)});
}
