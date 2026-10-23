import type { Graph } from "@/shared/types/logic/types";

// Tvar `GET /api/project-architecture/work-status` (docs/domeny-a-worktree.md §7, §9) a odvození
// pro dílky: pořadí „nejživější nahoře“, věta s počty, stránky, kterých se worktree dotýká.

export type WorktreeState = "running" | "waiting" | "stopped" | "none";
export type LiveSession = { source: "assistant" | "lease"; id: string; state: string | null; nodeId: string | null; lastSeenAt: string | null };
export type LiveCard = { nodeId: string; name: string };
export type LiveWorktree = { id: string; branch: string; actor: string; createdAt?: string; state: WorktreeState; reasons: string[]; sessions: LiveSession[]; cards: LiveCard[] };
export type LiveCounts = Record<WorktreeState, number> & { total: number };
export type LiveDomain = { id: string; name: string; environment: { name: string; host: string } | null; counts: LiveCounts; worktrees: LiveWorktree[] };
export type WorkStatus = { domains: LiveDomain[]; unassigned: LiveWorktree[]; mainSessions: LiveSession[] };

const STATES: WorktreeState[] = ["running", "waiting", "stopped", "none"];
const RANK: Record<WorktreeState, number> = { running: 0, waiting: 1, stopped: 2, none: 3 };
const text = (value: unknown) => (typeof value === "string" ? value : "");
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" ? value as Record<string, unknown> : {});

function session(raw: unknown): LiveSession {
  const item = record(raw);
  const source = item.source === "lease" ? "lease" : "assistant";
  return { source, id: text(item.id), state: text(item.state) || null, nodeId: text(item.nodeId) || null, lastSeenAt: text(item.lastSeenAt) || null };
}

function worktree(raw: unknown): LiveWorktree {
  const item = record(raw);
  const state = STATES.find((name) => name === item.state) ?? "none";
  return {
    id: text(item.id), branch: text(item.branch), actor: text(item.actor), ...(text(item.createdAt) ? { createdAt: text(item.createdAt) } : {}),
    state, reasons: list(item.reasons).map(text).filter(Boolean), sessions: list(item.sessions).map(session),
    cards: list(item.cards).map((card) => ({ nodeId: text(record(card).nodeId), name: text(record(card).name) || text(record(card).nodeId) })).filter((card) => card.nodeId),
  };
}

/** Nejživější nahoře: běží, čeká, stojí, bez relace; uvnitř stavu novější worktree první. */
export function sortWorktrees(items: LiveWorktree[]): LiveWorktree[] {
  return [...items].sort((a, b) => RANK[a.state] - RANK[b.state] || (b.createdAt ?? "").localeCompare(a.createdAt ?? "") || a.id.localeCompare(b.id));
}

export function countsOf(items: LiveWorktree[]): LiveCounts {
  const counts = { running: 0, waiting: 0, stopped: 0, none: 0, total: items.length };
  for (const item of items) counts[item.state] += 1;
  return counts;
}

/** Odpověď API na bezpečný tvar; chybějící pole jsou prázdná, worktree jsou seřazené. */
export function normalizeWorkStatus(raw: unknown): WorkStatus {
  const body = record(raw);
  const domains = list(body.domains).map((value): LiveDomain => {
    const item = record(value);
    const worktrees = sortWorktrees(list(item.worktrees).map(worktree));
    const env = record(item.environment);
    return { id: text(item.id), name: text(item.name), environment: item.environment ? { name: text(env.name), host: text(env.host) } : null, counts: countsOf(worktrees), worktrees };
  }).filter((domain) => domain.id);
  return { domains, unassigned: sortWorktrees(list(body.unassigned).map(worktree)), mainSessions: list(body.mainSessions).map(session) };
}

export function domainLive(status: WorkStatus | null, domainId: string): LiveDomain | null {
  return status?.domains.find((domain) => domain.id === domainId) ?? null;
}

/** „3 worktree · 1 běží · 1 čeká“; nulové stavy se vynechají, „bez relace“ se nepočítá zvlášť. */
export function countsLine(counts: LiveCounts): string {
  if (!counts.total) return "Žádný worktree";
  const parts = [`${counts.total} worktree`];
  if (counts.running) parts.push(`${counts.running} běží`);
  if (counts.waiting) parts.push(`${counts.waiting} čeká`);
  if (counts.stopped) parts.push(`${counts.stopped} stojí`);
  return parts.join(" · ");
}

/** Stránky (uzly `site.kind="page"`), pod kterými leží dané uzly: nejbližší stránka i její předkové. */
export function pagesTouched(graph: Graph, nodeIds: string[]): Set<string> {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const pages = new Set<string>();
  for (const start of nodeIds) {
    const seen = new Set<string>();
    let cursor = byId.get(start);
    while (cursor && !seen.has(cursor.id) && cursor.site?.kind !== "application") {
      seen.add(cursor.id);
      if (cursor.site?.kind === "page") pages.add(cursor.id);
      cursor = cursor.parentId ? byId.get(cursor.parentId) : undefined;
    }
  }
  return pages;
}

/** Kolik worktree se dotýká každé stránky (karty v práci a uzly relací); každý worktree jednou na stránku. */
export function pageWorkCounts(graph: Graph, worktrees: LiveWorktree[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const item of worktrees) {
    const ids = [...item.cards.map((card) => card.nodeId), ...item.sessions.map((s) => s.nodeId).filter((id): id is string => !!id)];
    for (const page of pagesTouched(graph, ids)) counts.set(page, (counts.get(page) ?? 0) + 1);
  }
  return counts;
}
