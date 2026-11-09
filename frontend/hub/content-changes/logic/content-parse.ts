import type { ContentScope, ContentEntry, ContentSummary, ContentProposal, ContentList, ContentDetail, ContentRebase } from "./content-changes";
type ObjectValue = Record<string, unknown>;
const object = (v: unknown): v is ObjectValue => !!v && typeof v === "object" && !Array.isArray(v);
const hash = (v: unknown, n = 40) => typeof v === "string" && new RegExp(`^[a-f0-9]{${n}}$`).test(v);
const nullableHash = (v: unknown) => v === null || hash(v);
const text = (v: unknown, max = 64000): v is string => typeof v === "string" && v.length <= max;
const count = (v: unknown, max: number) => Number.isSafeInteger(v) && (v as number) >= 0 && (v as number) <= max;
const fail = (): never => { throw new Error("Neúplné nebo neplatné podklady změny obsahu."); };
function entry(v: unknown): v is ContentEntry {
  if (!object(v) || !["text", "drawing", "storyboard", "config"].includes(String(v.kind)) || !text(v.target, 128) || !text(v.ownerWorkspace, 64)) return false;
  if (v.kind === "text") return v.field === "text" && text(v.value) && count(v.revision, Number.MAX_SAFE_INTEGER);
  if (v.kind === "drawing") return v.field === "scene" && object(v.value) && Array.isArray(v.value.elements) && count(v.revision, Number.MAX_SAFE_INTEGER);
  if (v.kind === "storyboard") return v.field === "storyboard" && count(v.revision, Number.MAX_SAFE_INTEGER)
    && (v.value === null || (object(v.value) && v.value.schema === "opora.storyboard/1" && Array.isArray(v.value.moments)));
  return ["actions", "rules", "blocks", "materials"].includes(String(v.field)) ? Array.isArray(v.value)
    : v.field === "downloadsUrl" && (v.value === null || typeof v.value === "boolean");
}
function summary(v: unknown): v is ContentSummary {
  return object(v) && hash(v.id) && v.kind === "content-proposal" && text(v.subject, 200) && object(v.by)
    && text(v.by.kind, 40) && text(v.by.name, 120) && text(v.createdAt, 80) && Number.isFinite(Date.parse(v.createdAt))
    && hash(v.parentRevision) && nullableHash(v.supersedes) && typeof v.requiresBaseContentAdoption === "boolean"
    && typeof v.accepted === "boolean" && count(v.changeCount, 128);
}
export function parseContentProposal(value: unknown, scope: ContentScope, expectedId?: string): ContentProposal {
  if (!object(value) || value.schemaVersion !== 1 || value.project !== scope.project || value.workspace !== scope.workspace
    || (expectedId !== undefined && value.id !== expectedId) || !summary({ ...value, accepted: false, changeCount: 0 })
    || !hash(value.graphDigest, 64) || !hash(value.baseContentDigest, 64)
    || !Array.isArray(value.baseContent) || value.baseContent.length > 16384 || !value.baseContent.every(entry)
    || !Array.isArray(value.changes) || value.changes.length < 1 || value.changes.length > 128) return fail();
  const keys = new Set<string>();
  for (const item of value.changes) {
    if (!object(item) || !Object.hasOwn(item, "before") || !Object.hasOwn(item, "acceptedBefore")
      || !entry({ ...item, ownerWorkspace: item.observedOwner, revision: item.observedRevision })
      || !(item.acceptedBefore === null || entry(item.acceptedBefore))
      || !(item.observedRound === null || (count(item.observedRound, Number.MAX_SAFE_INTEGER) && (item.observedRound as number) >= 1))) return fail();
    const key = JSON.stringify([item.kind, item.target, item.field]);
    if (keys.has(key)) return fail();
    keys.add(key);
    if (item.acceptedBefore && JSON.stringify([item.acceptedBefore.kind, item.acceptedBefore.target, item.acceptedBefore.field]) !== key) return fail();
  }
  return value as unknown as ContentProposal;
}
export function parseContentList(value: unknown): ContentList {
  if (!object(value) || !Array.isArray(value.items) || value.items.length > 100 || !value.items.every(summary)
    || new Set(value.items.map(item => item.id)).size !== value.items.length || !nullableHash(value.acceptedHead)
    || !nullableHash(value.contentManifestId) || typeof value.readOnly !== "boolean" || typeof value.canAccept !== "boolean"
    || (value.readOnly && value.canAccept)) return fail();
  return value as unknown as ContentList;
}
export function parseContentDetail(value: unknown, scope: ContentScope, id: string): ContentDetail {
  if (!object(value) || !nullableHash(value.accepted) || !nullableHash(value.acceptedHead)
    || typeof value.readOnly !== "boolean" || typeof value.canAccept !== "boolean" || ((value.readOnly || value.accepted !== null) && value.canAccept)) return fail();
  return { ...value, proposal: parseContentProposal(value.proposal, scope, id) } as ContentDetail;
}
export function parseContentRebase(value: unknown, scope: ContentScope): ContentRebase {
  if (!object(value) || typeof value.rebased !== "boolean" || !Array.isArray(value.conflicts) || value.conflicts.length > 128
    || !value.conflicts.every(v => object(v) && ["kind", "target", "field", "reason"].every(key => text(v[key], 2000)))) return fail();
  if (value.rebased ? value.conflicts.length > 0 || !value.proposal : value.proposal !== null || value.conflicts.length < 1) return fail();
  return { rebased: value.rebased, conflicts: value.conflicts, proposal: value.proposal ? parseContentProposal(value.proposal, scope) : null } as ContentRebase;
}
