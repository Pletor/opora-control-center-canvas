// Návrhy změn Správy webu od srdce (`backend/project/site_admin/proposals.py`): čtení čekajícího návrhu, přijetí nad
// revizí a zamítnutí (jen člověk, doklad UI přidá sdílené `api`) a čitelné řádky rozdílu. Bez Reactu.
import { api } from "@/shared/types/logic/types";
import type { SiteSaved } from "../../logic/site-admin-api";

export type ProposalChange = { path: string; before: unknown; after: unknown };
export type SiteProposal = { id: string; status: string; baseRevision: number; diff: ProposalChange[]; diffTotal: number;
  notes: string[]; note: string; by: string; at: string };
export type DiffLine = { path: string; before: string; after: string };

const BASE = "/api/site-admin/proposals";
const query = (project: string) => new URLSearchParams({ project }).toString();
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" ? value as Record<string, unknown> : {});

/** Čekající návrh (server drží nejvýš jeden) nebo null; cizí tvar odpovědi = null. */
export function pendingProposal(raw: unknown): SiteProposal | null {
  const items = record(raw).proposals;
  const first = Array.isArray(items) ? record(items[0]) : {};
  return typeof first.id === "string" && Array.isArray(first.diff) ? first as unknown as SiteProposal : null;
}

export const loadProposal = (project: string) => api<unknown>(`${BASE}?${query(project)}`).then(pendingProposal);
export const acceptProposal = (project: string, id: string, expectedRevision: number) =>
  api<SiteSaved>(`${BASE}/${encodeURIComponent(id)}/accept`, { project, expectedRevision });
export const rejectProposal = (project: string, id: string) => api<unknown>(`${BASE}/${encodeURIComponent(id)}/reject`, { project });

/** Hodnota listu rozdílu jako krátký text: chybějící „—“, text v uvozovkách, zbytek JSON; delší než `limit` se zkrátí. */
export function valueText(value: unknown, limit = 80): string {
  const text = value === null || value === undefined ? "—" : typeof value === "string" ? `„${value}“` : JSON.stringify(value);
  return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
}

export function diffLines(proposal: SiteProposal, limit = 12): DiffLine[] {
  return proposal.diff.slice(0, limit).map((change) => ({ path: change.path, before: valueText(change.before), after: valueText(change.after) }));
}
