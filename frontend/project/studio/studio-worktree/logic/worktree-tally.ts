// Práce ve worktree na kartách Skutečnosti (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §5): které worktree se
// karty týkají a kolik děr mainu je „v práci“. Karta patří worktree, když worktree zavírá nebo otevírá díru, jejíž
// místo řešení (`solverId`, jinak místo nálezu) je karta, nebo když na ní worktree drží lease / běžící relaci či kartu
// v práci (`work-status`). Rodič ve fraktálu sčítá worktree dětí stejně jako díry a strážce. Čistá logika bez Reactu.
import type { MapCheck, MapCheckFinding } from "@/project/architecture-editor/domain-site/map-check/logic/map-check";
import { findingKey, keyCard, type MapWorktreeOverlay } from "@/project/architecture-editor/domain-site/map-check/logic/map-check-worktrees";
import type { LiveSession, WorkStatus } from "@/project/architecture-editor/live-status/logic/live-model";

export type WorktreeMark = { workspaceId: string; branch: string; actor: string };
/** Worktree karty a jejích potomků (každý jednou, seřazené podle větve); `count` = počet různých worktree. */
export type WorktreeTally = { count: number; marks: WorktreeMark[] };
/** Kam nález patří na kartách (uzel, zdroj hrany, doména cesty); chybí = nikam. */
export type FindingLocate = (finding: MapCheckFinding) => string | undefined;

/** Živý nárok práce: lease `active`. */
export const sessionLive = (session: LiveSession) => session.state === "active";

/** Worktree po kartách z overlay kontroly mapy a ze stavu práce; obojí může chybět. */
export function worktreesByNode(overlay: MapWorktreeOverlay | null | undefined, work: WorkStatus | null | undefined, locate: FindingLocate): Map<string, WorktreeMark[]> {
  const byNode = new Map<string, Map<string, WorktreeMark>>();
  const add = (nodeId: string | undefined, mark: WorktreeMark) => {
    if (!nodeId) return;
    const marks = byNode.get(nodeId) ?? new Map<string, WorktreeMark>();
    if (!marks.has(mark.workspaceId)) marks.set(mark.workspaceId, mark);
    byNode.set(nodeId, marks);
  };
  const place = (finding: MapCheckFinding) => finding.solverId ?? locate(finding);
  const main = new Map((overlay?.main ?? []).map((finding) => [findingKey(finding), finding]));
  for (const worktree of overlay?.worktrees ?? []) {
    const mark = { workspaceId: worktree.workspaceId, branch: worktree.branch, actor: worktree.actor };
    for (const key of worktree.closed) { const finding = main.get(key); add(finding ? place(finding) : keyCard(key), mark); }
    for (const finding of worktree.opened) add(place(finding), mark);
  }
  for (const worktree of work ? [...work.domains.flatMap((domain) => domain.worktrees), ...work.unassigned] : []) {
    const mark = { workspaceId: worktree.id, branch: worktree.branch || worktree.id, actor: worktree.actor };
    for (const session of worktree.sessions) if (session.nodeId && sessionLive(session)) add(session.nodeId, mark);
    for (const card of worktree.cards) add(card.nodeId, mark);
  }
  return new Map([...byNode].map(([nodeId, marks]) => [nodeId, [...marks.values()]]));
}

/** Díry mainu „v práci“ po kartách: nález mainu, který některý aktivní worktree zavírá, na místě jako díra (`locate`). */
export function holesInWork(overlay: MapWorktreeOverlay | null | undefined, check: MapCheck | null | undefined, locate: FindingLocate): Map<string, number> {
  const counts = new Map<string, number>();
  const closed = new Set((overlay?.worktrees ?? []).flatMap((worktree) => worktree.closed));
  if (!closed.size || !check) return counts;
  for (const finding of check.findings) {
    const nodeId = closed.has(findingKey(finding)) ? locate(finding) : undefined;
    if (nodeId) counts.set(nodeId, (counts.get(nodeId) ?? 0) + 1);
  }
  return counts;
}

/** Součet worktree karet (karta a potomci): každý worktree jednou; bez jediného `null`. */
export function sumWorktrees(lists: Iterable<WorktreeMark[] | null | undefined>): WorktreeTally | null {
  const marks = new Map<string, WorktreeMark>();
  for (const list of lists) for (const mark of list ?? []) if (!marks.has(mark.workspaceId)) marks.set(mark.workspaceId, mark);
  if (!marks.size) return null;
  const sorted = [...marks.values()].sort((a, b) => a.branch.localeCompare(b.branch) || a.workspaceId.localeCompare(b.workspaceId));
  return { count: sorted.length, marks: sorted };
}

/** Text odznaku: jeden worktree = jméno větve, víc = „2 worktree“. */
export const worktreeBadgeText = (tally: WorktreeTally) => (tally.count === 1 ? tally.marks[0].branch : `${tally.count} worktree`);

/** Věta pro title a čtečku: „Ve worktree se pracuje: feat/a (agent-1), feat/b“. */
export const worktreeLabel = (tally: WorktreeTally) =>
  "Ve worktree se pracuje: " + tally.marks.map((mark) => mark.branch + (mark.actor ? ` (${mark.actor})` : "")).join(", ");
