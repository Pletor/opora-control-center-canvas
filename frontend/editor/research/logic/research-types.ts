export type ResearchScope = { project: string; workspace: string };
export type ResearchRefs = { nodeIds: string[]; questionIds: string[]; ticketIds: string[]; sessionIds: string[]; fragmentIds: string[]; attachmentIds: string[] };
export type Verification = { status: "unverified" | "verified" | "observed" | "false" | "unreachable" | "inference" | "conflict"; method: string; at: string };
export type Source = { ref: string; platform: string; quote: string; title: string; accessedAt: string; timestamp?: string; revision?: string; location?: string; discoveredVia?: string; verification?: Verification };
export type ResearchHeader = {
  id: string; revision: number; kind: "question" | "finding" | "visual" | "option" | "decision";
  title: string; summary: string; topicPath: string[]; status: "open" | "resolved";
  verification: Verification; refs: ResearchRefs; archived: boolean; createdAt: string; updatedAt: string; by: string;
  platforms: string[]; sourceCount: number;
  relationCounts?: { incoming: number; outgoing: number };
};
export type ResearchCard = Omit<ResearchHeader, "platforms" | "sourceCount" | "relationCounts"> & { content: string; sources: Source[] };
export type ResearchEdge = {
  id: string; revision: number; fromId: string; toId: string;
  relation: "supports" | "contradicts" | "elaborates" | "option_for" | "supersedes" | "resolves" | "continues_to";
  reason: string; resolved: string; missing: string; evidenceIds: string[]; archived: boolean;
};
export type ResearchGraph = { workspace?: string; cards: ResearchHeader[]; edges: ResearchEdge[] };
export type ResearchDetail = { card: ResearchCard; history: { revision: number; updatedAt?: string; createdAt?: string; by?: string }[]; edges: ResearchEdge[] };

export type ResearchEdgeDetail = { edge: ResearchEdge; history: ResearchDetail["history"] };
