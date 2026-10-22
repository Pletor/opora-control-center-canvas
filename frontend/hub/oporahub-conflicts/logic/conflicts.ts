import { isNullableText, isObject, isText, scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";

// Drátový tvar konfliktů auto-rebase (docs/oporahub-auto-rebase.md) a čisté view-modely pro drawer.
export type ConflictStatus = "open" | "resolved" | "obsolete";
export type ConflictField = { key: string; base: unknown; ours: unknown; theirs: unknown };
export type Conflict = {
  id: string; status: ConflictStatus; resolutionProposalId: string | null; createdAt: string; updatedAt: string;
  proposalKind: string; proposalId: string; acceptedHead: string | null; items: ConflictField[];
};
export type ConflictList = { items: Conflict[]; acceptedHead: string | null; enabled: boolean };
export type Side = "ours" | "theirs";
export type Choices = Record<string, Side>;
export type StatusFilter = ConflictStatus | "all";

const STATUSES: ConflictStatus[] = ["open", "resolved", "obsolete"];
const field = (value: unknown): value is ConflictField => isObject(value) && isText(value.key);
function conflict(value: unknown): value is Record<string, unknown> {
  return isObject(value) && isText(value.id) && STATUSES.includes(value.status as ConflictStatus)
    && isNullableText(value.resolutionProposalId ?? null) && isText(value.proposalId) && isText(value.proposalKind)
    && Array.isArray(value.items) && value.items.every(field);
}
export function parseConflicts(raw: unknown): ConflictList {
  if (!isObject(raw) || !Array.isArray(raw.items) || !raw.items.every(conflict)) throw new Error("Konflikty auto-rebase mají neplatný tvar.");
  const items = raw.items.map((item): Conflict => ({
    id: item.id as string, status: item.status as ConflictStatus, resolutionProposalId: (item.resolutionProposalId as string | null) ?? null,
    createdAt: String(item.createdAt ?? ""), updatedAt: String(item.updatedAt ?? ""), proposalKind: item.proposalKind as string,
    proposalId: item.proposalId as string, acceptedHead: isText(item.acceptedHead) ? item.acceptedHead : null,
    items: (item.items as Record<string, unknown>[]).map(entry => ({ key: entry.key as string, base: entry.base, ours: entry.ours, theirs: entry.theirs })),
  }));
  return { items, acceptedHead: isText(raw.acceptedHead) ? raw.acceptedHead : null, enabled: raw.enabled !== false };
}
export const conflictsUrl = (project: string, workspace: string, status: StatusFilter) =>
  `/api/oporahub/auto-rebase/conflicts?${scopeQuery(status === "all" ? { project, workspace } : { project, workspace, status })}`;
export const resolveUrl = (id: string) => `/api/oporahub/auto-rebase/conflicts/${encodeURIComponent(id)}/resolve`;
export const RUN_URL = "/api/oporahub/auto-rebase/run";

export const STATUS_LABEL: Record<ConflictStatus, string> = { open: "otevřený", resolved: "vyřešený", obsolete: "zastaralý" };
export const STATUS_GLYPH: Record<ConflictStatus, string> = { open: "◷", resolved: "✓", obsolete: "◌" };
export const KIND_LABEL: Record<string, string> = { spec: "zadání", changeset: "zadání", "graph-additions": "přírůstek grafu",
  "graph-change": "změna grafu", content: "obsah" };

/** Kompaktní zobrazení hodnoty pole: text doslova, chybějící hodnota jako „—“, ostatní jako JSON. */
export function showValue(value: unknown): string {
  if (value === undefined || value === null) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

export type FieldRow = { key: string; base: string; ours: string; theirs: string; oursChanged: boolean; theirsChanged: boolean; choice: Side | "" };
/** Řádek pole: která strana se od `base` liší (obě = skutečný konflikt stejného pole). */
export function fieldRows(item: Conflict, choices: Choices): FieldRow[] {
  return item.items.map(entry => ({ key: entry.key, base: showValue(entry.base), ours: showValue(entry.ours), theirs: showValue(entry.theirs),
    oursChanged: !same(entry.ours, entry.base), theirsChanged: !same(entry.theirs, entry.base), choice: choices[entry.key] ?? "" }));
}

/** Návrh řešení pro nový návrh nad aktuální hlavou: zvolená hodnota každého pole; nevybrané pole zůstává otevřené. */
export function resolutionDraft(item: Conflict, choices: Choices): { text: string; complete: boolean } {
  const lines = item.items.map(entry => {
    const side = choices[entry.key];
    if (!side) return `- ${entry.key}: NEROZHODNUTO (návrh ${showValue(entry.ours)} × hlava ${showValue(entry.theirs)})`;
    return `- ${entry.key}: ${showValue(side === "ours" ? entry.ours : entry.theirs)} (${side === "ours" ? "z návrhu" : "z aktuální hlavy"})`;
  });
  return { complete: item.items.every(entry => !!choices[entry.key]),
    text: [`Řešení konfliktu ${item.id.slice(0, 12)} · ${KIND_LABEL[item.proposalKind] ?? item.proposalKind} ${item.proposalId}`,
      `Nad hlavou ${item.acceptedHead?.slice(0, 12) ?? "?"}:`, ...lines].join("\n") };
}

export function resolveError(status: number | undefined, message: string) {
  if (status === 409 || status === 400 || status === 422) return "Řešení musí být jiný návrh nad aktuální hlavou.";
  if (status === 403) return "Tuto operaci smí provést jen člověk.";
  return message || "Připojení řešení se nezdařilo.";
}
export const validProposalId = (value: string) => /^[A-Za-z0-9_.:-]{1,128}$/.test(value.trim());
