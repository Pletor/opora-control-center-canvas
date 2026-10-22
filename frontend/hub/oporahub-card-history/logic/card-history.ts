import { isObject, isText, scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";

// Odvozená historie a blame karty (docs/oporahub-auto-rebase.md, „Odvozená data“). Autor může být objekt
// `{kind, name}`, prostý text nebo null; parser je tolerantní k tvaru autora, přísný na revizi.
export type RevisionMeta = {
  revisionId: string; parentRevision: string | null; revisionKind: string; proposalId: string | null; proposalKind: string | null;
  subject: string; author: unknown; originalAuthor: unknown; rebasedFrom: string | null; acceptedBy: unknown; acceptedAt: string;
};
export type HistoryItem = RevisionMeta & { changedKeys: string[] };
export type BlameItem = RevisionMeta & { key: string };
export type CardHistoryDoc = { cardId: string; acceptedHead: string | null; items: HistoryItem[] };
export type CardBlameDoc = { cardId: string; acceptedHead: string | null; items: BlameItem[] };

const optional = (value: unknown) => isText(value) ? value : null;
function meta(value: Record<string, unknown>): RevisionMeta {
  return { revisionId: value.revisionId as string, parentRevision: optional(value.parentRevision), revisionKind: String(value.revisionKind ?? ""),
    proposalId: optional(value.proposalId), proposalKind: optional(value.proposalKind), subject: isText(value.subject) ? value.subject : "",
    author: value.author ?? null, originalAuthor: value.originalAuthor ?? null, rebasedFrom: optional(value.rebasedFrom),
    acceptedBy: value.acceptedBy ?? null, acceptedAt: isText(value.acceptedAt) ? value.acceptedAt : "" };
}
function doc(raw: unknown, label: string) {
  if (!isObject(raw) || !isText(raw.cardId) || !Array.isArray(raw.items)
    || !raw.items.every(item => isObject(item) && isText(item.revisionId))) throw new Error(`${label} karty má neplatný tvar.`);
  return { cardId: raw.cardId, acceptedHead: optional(raw.acceptedHead), items: raw.items as Record<string, unknown>[] };
}
export function parseHistory(raw: unknown): CardHistoryDoc {
  const value = doc(raw, "Historie");
  return { ...value, items: value.items.map(item => ({ ...meta(item),
    changedKeys: Array.isArray(item.changedKeys) ? item.changedKeys.filter((key): key is string => isText(key)) : [] })) };
}
export function parseBlame(raw: unknown): CardBlameDoc {
  const value = doc(raw, "Blame");
  if (!value.items.every(item => isText(item.key))) throw new Error("Blame karty má neplatný klíč.");
  return { ...value, items: value.items.map(item => ({ ...meta(item), key: item.key as string })) };
}
const path = (kind: "history" | "blame", project: string, workspace: string, card: string) =>
  `/api/oporahub/${kind}/card/${encodeURIComponent(card)}?${scopeQuery({ project, workspace })}`;
export const historyUrl = (project: string, workspace: string, card: string) => path("history", project, workspace, card);
export const blameUrl = (project: string, workspace: string, card: string) => path("blame", project, workspace, card);

/** Jméno autora z libovolného tvaru; neznámý autor je „neznámý“, nikdy se nevymýšlí. */
export function authorName(value: unknown): string {
  if (isText(value) && value) return value;
  if (isObject(value)) {
    const name = isText(value.name) && value.name ? value.name : "";
    const kind = isText(value.kind) ? value.kind : "";
    return name && kind && kind !== "human" ? `${name} (${kind})` : name || kind || "neznámý";
  }
  return "neznámý";
}
const short = (value: string | null) => value ? value.slice(0, 10) : "—";
const when = (value: string) => value ? value.slice(0, 16).replace("T", " ") : "—";

export type HistoryRow = { revisionId: string; short: string; subject: string; author: string; rebased: string; acceptedBy: string;
  acceptedAt: string; keys: string[]; proposalId: string; current: boolean };
/** Historie od nejnovější revize; auto-rebase uvádí původního autora a zdrojový návrh. */
export function historyRows(history: CardHistoryDoc): HistoryRow[] {
  return [...history.items].reverse().map(item => {
    const author = authorName(item.author), original = authorName(item.originalAuthor);
    const rebased = item.rebasedFrom || original !== author ? `auto-rebase z ${short(item.rebasedFrom)} · původně ${original}` : "";
    return { revisionId: item.revisionId, short: short(item.revisionId), subject: item.subject || "(bez předmětu)", author, rebased,
      acceptedBy: authorName(item.acceptedBy), acceptedAt: when(item.acceptedAt), keys: item.changedKeys, proposalId: item.proposalId ?? "",
      current: item.revisionId === history.acceptedHead };
  });
}
export type BlameRow = { key: string; revisionId: string; short: string; author: string; acceptedAt: string };
export function blameRows(blame: CardBlameDoc): BlameRow[] {
  return blame.items.map(item => ({ key: item.key, revisionId: item.revisionId, short: short(item.revisionId),
    author: authorName(item.originalAuthor ?? item.author), acceptedAt: when(item.acceptedAt) }));
}
