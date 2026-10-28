// Kontrola mapy přes worktree (`GET /api/project-architecture/map-check/worktrees?project=`, kontrakt
// docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §3): díry mainu a pro každý aktivní worktree, které díry mainu
// zavírá (`closed`, klíče) a které nové otevírá (`opened`, nálezy). Čistá logika bez Reactu: adresa, klíč nálezu
// a obranné čtení odpovědi. Chybějící endpoint nebo neznámý tvar = žádné worktree, nikdy výjimka.
import { normalizeMapCheck, type MapCheckFinding } from "./map-check";

export type MapWorktree = {
  workspaceId: string; branch: string; actor: string; domainId: string | null;
  /** Klíče nálezů mainu, které ve worktree už nejsou (díra je „v práci“). */
  closed: string[];
  /** Nálezy worktree, které na mainu nejsou (nové díry, které práce cestou otevírá). */
  opened: MapCheckFinding[];
};
export type MapWorktreeOverlay = { main: MapCheckFinding[]; worktrees: MapWorktree[] };

export function mapWorktreesUrl(project: string): string {
  return "/api/project-architecture/map-check/worktrees?" + new URLSearchParams({ project });
}

/** Klíč nálezu `rule|nodeId|edgeId|journeyId|solverId|message` (chybějící část prázdná), stejný jako backend (W1).
 * Nálezy se čtou s `locate=1`, takže `solverId` mají obě strany porovnání. */
export const findingKey = (finding: MapCheckFinding) =>
  [finding.rule, finding.nodeId ?? "", finding.edgeId ?? "", finding.journeyId ?? "", finding.solverId ?? "", finding.message].join("|");

/** Karta zavřené díry přímo z klíče: 5. část (`solverId`), jinak `nodeId`; zpráva smí obsahovat „|“. */
export function keyCard(key: string): string | undefined {
  const parts = key.split("|");
  return parts[4] || parts[1] || undefined;
}

const text = (value: unknown) => (typeof value === "string" ? value : "");
const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" ? value as Record<string, unknown> : {});
const findings = (value: unknown) => normalizeMapCheck({ findings: value }).findings;

/** Odpověď API na bezpečný tvar: worktree bez `workspaceId` se zahodí, `closed` jen neprázdné řetězce. */
export function normalizeWorktreeOverlay(raw: unknown): MapWorktreeOverlay {
  const body = record(raw);
  const worktrees = (Array.isArray(body.worktrees) ? body.worktrees : []).flatMap((value): MapWorktree[] => {
    const item = record(value);
    const workspaceId = text(item.workspaceId);
    if (!workspaceId) return [];
    const closed = (Array.isArray(item.closed) ? item.closed : []).map(text).filter(Boolean);
    return [{ workspaceId, branch: text(item.branch) || workspaceId, actor: text(item.actor), domainId: text(item.domainId) || null, closed, opened: findings(item.opened) }];
  });
  return { main: findings(body.main), worktrees };
}

/** Otisk overlay pro memoizaci: stejná odpověď = stejný řetězec, takže opakované čtení nepřepočítá karty. */
export const overlayKey = (overlay: MapWorktreeOverlay | null) => (overlay && overlay.worktrees.length ? JSON.stringify(overlay) : "");
