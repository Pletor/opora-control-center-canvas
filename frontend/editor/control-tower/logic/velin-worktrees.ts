// Práce ve worktree ve Velínu (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §5): řádek na aktivní worktree
// „větev · aktér · zavírá N děr · otevírá M nových“ a pod ním nové díry, které práce cestou otevírá. Tady člověk
// kontroluje práci po cestě a může změnit směr. Zdroj je jen kontrola mapy přes worktree; čisté funkce, nic se neodhaduje.
import { MAP_CHECK_TEXT, type MapCheckFinding } from "@/project/architecture-editor/domain-site/map-check/logic/map-check";
import { findingKey, type MapWorktreeOverlay } from "@/project/architecture-editor/domain-site/map-check/logic/map-check-worktrees";

export type VelinNewHole = { key: string; message: string; ruleLabel: string; nodeId: string | null; cardName: string };
export type VelinWorktreeRow = { workspaceId: string; branch: string; actor: string; closed: number; opened: VelinNewHole[] };

/** Řádky worktree v pořadí serveru; nová díra míří na místo řešení (`solverId`), jinak na místo nálezu (`locate`). */
export function velinWorktrees(overlay: MapWorktreeOverlay | null, locate: (finding: MapCheckFinding) => string | null, nameOf: (id: string) => string): VelinWorktreeRow[] {
  return (overlay?.worktrees ?? []).map((worktree) => ({
    workspaceId: worktree.workspaceId, branch: worktree.branch, actor: worktree.actor, closed: worktree.closed.length,
    opened: worktree.opened.map((finding) => {
      const nodeId = finding.solverId ?? locate(finding);
      return { key: findingKey(finding), message: finding.message, ruleLabel: MAP_CHECK_TEXT[finding.rule].label, nodeId, cardName: nodeId ? nameOf(nodeId) : "" };
    }),
  }));
}

const plural = (count: number, one: string, few: string, many: string) => `${count} ${count === 1 ? one : count > 1 && count < 5 ? few : many}`;

/** „zavírá 2 díry · otevírá 1 novou“. */
export const worktreeWorkLine = (row: Pick<VelinWorktreeRow, "closed"> & { opened: unknown[] }) =>
  `zavírá ${plural(row.closed, "díru", "díry", "děr")} · otevírá ${plural(row.opened.length, "novou", "nové", "nových")}`;
