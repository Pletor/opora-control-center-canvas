// Skladiště uzavřených worktree (docs/domeny-a-worktree.md §6, §13.3): přesun s povinným důvodem
// a seznam jen ke čtení (`GET /api/workspaces/archive`). Větev `work/<wid>` po přesunu zůstává.

export type ArchivedWorktree = { id: string; nodeId: string; branch: string; actor: string; reason: string; archivedAt: string };
/** Seznam skladiště v editoru: `items = null` = ještě nenačteno. */
export type ArchiveShelfState = { items: ArchivedWorktree[] | null; loading: boolean; error: string };

export const REASON_LIMIT = 500;
export const emptyShelf = (): ArchiveShelfState => ({ items: null, loading: false, error: "" });

const text = (value: unknown) => (typeof value === "string" ? value : "");

/** Odpověď API na bezpečný seznam; položky bez ID se zahodí, nejnovější první. */
export function normalizeArchive(raw: unknown): ArchivedWorktree[] {
  const body = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
  const items = Array.isArray(body.items) ? body.items : [];
  return items.map((value) => {
    const item = value && typeof value === "object" ? value as Record<string, unknown> : {};
    return { id: text(item.id), nodeId: text(item.nodeId), branch: text(item.branch), actor: text(item.actor), reason: text(item.reason), archivedAt: text(item.archivedAt) };
  }).filter((item) => item.id).sort((a, b) => b.archivedAt.localeCompare(a.archivedAt));
}

/** Prázdný nebo příliš dlouhý důvod řekne větou, jinak `""`. */
export function reasonProblem(reason: string): string {
  const trimmed = reason.trim();
  if (!trimmed) return "Napište, proč worktree končí (třeba „nápad nevyšel“).";
  if (trimmed.length > REASON_LIMIT) return `Důvod je delší než ${REASON_LIMIT} znaků.`;
  return "";
}

/** „14. 10. 2026 12:03“ v místním čase; nečitelné datum se ukáže tak, jak přišlo. */
export function archivedDate(iso: string): string {
  const moment = new Date(iso);
  if (!iso || Number.isNaN(moment.getTime())) return iso;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${moment.getDate()}. ${moment.getMonth() + 1}. ${moment.getFullYear()} ${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
}

/** Proč tlačítko „Do skladiště“ nejde použít; `""` = jde. Ostatní odmítnutí (změny, živá relace) říká backend. */
export function archiveBlocked(worktreeId: string, currentWorkspace: string): string {
  return worktreeId === currentWorkspace ? "V tomto worktree právě pracujete. Nejdřív se přepněte jinam." : "";
}
