export const CONTENT_ROOT = "/api/oporahub/content-changes";
export type ContentScope = { project: string; workspace: string };
export type ContentEntry = { kind: "text" | "drawing" | "config"; target: string; field: string; ownerWorkspace: string; value: unknown; revision?: number };
export type ContentChange = Pick<ContentEntry, "kind" | "target" | "field" | "value"> & {
  before: unknown; acceptedBefore: ContentEntry | null; observedOwner: string; observedRevision?: number; observedRound: number | null };
export type ContentSummary = { id: string; kind: "content-proposal"; subject: string; by: { kind: string; name: string }; createdAt: string;
  parentRevision: string; supersedes: string | null; requiresBaseContentAdoption: boolean; accepted: boolean; changeCount: number };
export type ContentProposal = Omit<ContentSummary, "accepted" | "changeCount"> & ContentScope & {
  schemaVersion: 1; graphDigest: string; baseContentDigest: string; baseContent: ContentEntry[]; changes: ContentChange[] };
export type ContentList = { items: ContentSummary[]; acceptedHead: string | null; contentManifestId: string | null; readOnly: boolean; canAccept: boolean };
export type ContentDetail = { proposal: ContentProposal; accepted: string | null; acceptedHead: string | null; readOnly: boolean; canAccept: boolean };
export type ContentConflict = { kind: string; target: string; field: string; reason: string };
export type ContentRebase = { proposal: ContentProposal | null; rebased: boolean; conflicts: ContentConflict[] };
export const contentQuery = (scope: ContentScope) => new URLSearchParams(scope).toString();
export function contentDetailUrl(scope: ContentScope, id: string) {
  if (!/^[a-f0-9]{40}$/.test(id)) throw new Error("Neplatné ID návrhu obsahu.");
  return `${CONTENT_ROOT}/${id}?${contentQuery(scope)}`;
}
export function contentAcknowledgement(proposal: ContentProposal) { return `${proposal.id}:${proposal.baseContentDigest}`; }
export function contentAction(scope: ContentScope, list: ContentList, detail: ContentDetail, kind: "accept" | "rebase", ack: string) {
  const item = detail.proposal;
  if (item.project !== scope.project || item.workspace !== scope.workspace || list.readOnly || detail.readOnly
    || detail.accepted || !list.acceptedHead || list.acceptedHead !== detail.acceptedHead)
    throw new Error("Podklady návrhu nejsou aktuální nebo jsou jen ke čtení.");
  const basis = { ...scope, expectedAcceptedHead: list.acceptedHead };
  if (kind === "rebase") return basis;
  if (!list.canAccept || !detail.canAccept || item.parentRevision !== list.acceptedHead)
    throw new Error("Přijetí vyžaduje člověka a návrh nad aktuální přijatou revizí.");
  if (item.requiresBaseContentAdoption && ack !== contentAcknowledgement(item))
    throw new Error("Potvrďte celý přesný výchozí obsah, který návrh přebírá.");
  return { ...basis, reviewedProposalId: item.id, adoptBaseContentDigest: item.requiresBaseContentAdoption ? item.baseContentDigest : null };
}
/** Independent request generations fence stale scope/ID responses and duplicate writes. */
export class ContentRequests {
  private key = ""; private generation = 0; private writing = false;
  context(key: string) { if (this.key !== key) { this.key = key; this.invalidate(); } }
  next() { const ticket = ++this.generation; return () => ticket === this.generation; }
  invalidate() { this.generation++; }
  beginWrite() { if (this.writing) return null; this.writing = true; return this.next(); }
  endWrite() { this.writing = false; }
  get busy() { return this.writing; }
}
export function contentValue(value: unknown) {
  const full = value === undefined ? "Nedoloženo" : value === null ? "Chybí v přijatém obsahu" : typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return { full, preview: full.length > 8000 ? full.slice(0, 8000) + "\n… Zobrazení zkráceno; celý obsah je v JSON návrhu." : full };
}
