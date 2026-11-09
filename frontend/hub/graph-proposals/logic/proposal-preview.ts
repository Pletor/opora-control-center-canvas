import type { GraphProposal } from "./graph-proposals";
import type { Graph } from "@/shared/types/logic/types";

/** Only project the immutable server proposal; v2 result is authoritative, never replay edits here. */
export function proposalPreview(proposal: GraphProposal): Graph | null {
  if ([2, 3, 4].includes(proposal.schemaVersion ?? 1)) return proposal.resultGraph ?? null;
  return { nodes: [...proposal.baseGraph.nodes, ...proposal.additions.nodes],
    edges: [...proposal.baseGraph.edges, ...proposal.additions.edges] };
}

/** Initial camera targets persisted additions/changes; an empty target means fit the full graph. */
export function proposalFocus(proposal: GraphProposal): { id: string }[] | undefined {
  const present = new Set(proposalPreview(proposal)?.nodes.map(node => node.id) ?? []);
  const added = proposal.additions.nodes.filter(node => present.has(node.id)).map(({ id }) => ({ id }));
  if (added.length) return added;
  const changed = (proposal.changes?.nodes ?? []).filter(node => present.has(node.id)).map(({ id }) => ({ id }));
  return changed.length ? changed : undefined;
}

export function scopedProposalLink(search: string, project: string, workspace: string): string {
  const params = new URLSearchParams(search);
  if (params.get("project") !== project || params.get("workspace") !== workspace) return "";
  const id = params.get("ohGraph") ?? "";
  return /^[a-zA-Z0-9_-]{1,160}$/.test(id) ? id : "";
}
