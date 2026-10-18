import type { LiveWorktree } from "./live-model";

// Klávesnice ve stromu worktree (vzor WAI-ARIA Tree View): ve stromu je vždy jen jedna položka
// v pořadí Tab (roving tabindex). Šipky nahoru/dolů jdou po viditelných položkách, vpravo rozbalí
// worktree nebo skočí na první dítě, vlevo sbalí nebo vrátí na rodiče, Home/End na kraje,
// Enter/mezera položku použije (worktree vybere, relaci nebo kartu otevře).

export type TreeItem = { key: string; level: 1 | 2; worktreeId: string; kind: "worktree" | "session" | "card"; targetId: string };
export type TreeMove = { focus?: string; expand?: string; collapse?: string; activate?: TreeItem } | null;

export const worktreeKey = (id: string) => `w:${id}`;

/** Položky v pořadí, jak je čtečka i šipky vidí: worktree, pod rozbaleným jeho relace a karty. */
export function visibleItems(worktrees: LiveWorktree[], open: ReadonlySet<string>): TreeItem[] {
  return worktrees.flatMap((worktree): TreeItem[] => {
    const head: TreeItem = { key: worktreeKey(worktree.id), level: 1, worktreeId: worktree.id, kind: "worktree", targetId: worktree.id };
    if (!open.has(worktree.id)) return [head];
    return [
      head,
      ...worktree.sessions.map((session): TreeItem => ({ key: `s:${worktree.id}:${session.source}:${session.id}`, level: 2, worktreeId: worktree.id, kind: "session", targetId: session.id })),
      ...worktree.cards.map((card): TreeItem => ({ key: `c:${worktree.id}:${card.nodeId}`, level: 2, worktreeId: worktree.id, kind: "card", targetId: card.nodeId })),
    ];
  });
}

/** Položka v pořadí Tab: zaměřená, pokud ještě je vidět, jinak první. */
export function tabStop(items: TreeItem[], focused: string | null): string | null {
  return items.some((item) => item.key === focused) ? focused : items[0]?.key ?? null;
}

/** Co udělat po stisku klávesy na položce `current`; `null` = klávesa stromu nepatří. */
export function treeKey(items: TreeItem[], current: string, key: string, open: ReadonlySet<string>): TreeMove {
  const index = items.findIndex((item) => item.key === current);
  if (index < 0) return null;
  const item = items[index];
  const parent = worktreeKey(item.worktreeId);
  switch (key) {
    case "ArrowDown": return { focus: items[Math.min(index + 1, items.length - 1)].key };
    case "ArrowUp": return { focus: items[Math.max(index - 1, 0)].key };
    case "Home": return { focus: items[0].key };
    case "End": return { focus: items[items.length - 1].key };
    case "ArrowRight":
      if (item.level === 2) return {};
      if (!open.has(item.worktreeId)) return { expand: item.worktreeId };
      return items[index + 1]?.level === 2 ? { focus: items[index + 1].key } : {};
    case "ArrowLeft":
      if (item.level === 2) return { focus: parent };
      return open.has(item.worktreeId) ? { collapse: item.worktreeId } : {};
    case "Enter": case " ": return { activate: item };
    default: return null;
  }
}
