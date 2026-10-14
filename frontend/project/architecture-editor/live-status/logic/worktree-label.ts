// Jak se worktree jmenuje na obrazovce. Člověk worktree poznává podle aktéra (kdo / proč na něm
// pracuje) a krátkého ID; větev `work/<40 znaků>` je technická podrobnost, proto jde jen do `title`.

type Named = { id: string; branch?: string; actor?: string };
export type WorktreeLabel = { title: string; shortId: string; branch: string; tooltip: string };

/** Prvních 8 znaků ID worktree (stejně jako krátký SHA v Gitu). */
export function shortWorktreeId(id: string): string {
  return id.trim().slice(0, 8);
}

/** Hlavní popisek = aktér, jinak krátké ID, jinak větev; větev a plné ID jsou jen v `tooltip`. */
export function worktreeLabel(worktree: Named): WorktreeLabel {
  const actor = (worktree.actor ?? "").trim();
  const branch = (worktree.branch ?? "").trim();
  const shortId = shortWorktreeId(worktree.id);
  const title = actor || shortId || branch;
  const tooltip = [worktree.id && `Worktree ${worktree.id}`, branch && `větev ${branch}`, actor && `aktér ${actor}`].filter(Boolean).join(" · ");
  return { title, shortId, branch, tooltip };
}

/** Jednořádkové jméno do vět a názvů relací: „01-start-projektu · a0f1764b“. */
export function worktreeName(worktree: Named): string {
  const { title, shortId } = worktreeLabel(worktree);
  return !shortId || title === shortId ? title : `${title} · ${shortId}`;
}
