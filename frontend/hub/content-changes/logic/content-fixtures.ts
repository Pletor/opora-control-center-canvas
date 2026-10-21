/** Test-only fixtures; runtime readers never import this module. */
import type { ContentDetail, ContentList, ContentProposal } from "./content-changes";
export const contentScope = { project: "project", workspace: "work" };
export function contentProposal(): ContentProposal {
  return { ...contentScope, id: "a".repeat(40), kind: "content-proposal", schemaVersion: 1, subject: "Změna <script> obsahu",
    by: { kind: "agent", name: "Worker" }, createdAt: "2026-10-21T12:00:00Z", parentRevision: "b".repeat(40), supersedes: null,
    requiresBaseContentAdoption: true, graphDigest: "c".repeat(64), baseContentDigest: "d".repeat(64),
    baseContent: [{ kind: "text", target: "card", field: "text", ownerWorkspace: "work", revision: 0, value: "Original" }],
    changes: [{ kind: "text", target: "card", field: "text", before: "Working", value: "Desired",
      acceptedBefore: null, observedOwner: "work", observedRevision: 1, observedRound: 2 }] };
}
export function contentList(): ContentList {
  const { id, kind, subject, by, createdAt, parentRevision, supersedes, requiresBaseContentAdoption } = contentProposal();
  return { items: [{ id, kind, subject, by, createdAt, parentRevision, supersedes, requiresBaseContentAdoption, accepted: false, changeCount: 1 }],
    acceptedHead: parentRevision, contentManifestId: null, readOnly: false, canAccept: true };
}
export function contentDetail(): ContentDetail {
  return { proposal: contentProposal(), accepted: null, acceptedHead: contentProposal().parentRevision, readOnly: false, canAccept: true };
}
