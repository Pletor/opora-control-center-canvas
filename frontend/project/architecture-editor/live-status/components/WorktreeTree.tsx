import { useRef, useState, type KeyboardEvent } from "react";
import "../styles/live-status.css";
import type { LiveWorktree } from "../logic/live-model";
import { tabStop, treeKey, visibleItems, type TreeItem } from "../logic/tree-nav";
import WorktreeRow, { type WorktreeNav } from "./WorktreeRow";

/**
 * Strom worktree (`role="tree"`): nejživější nahoře (pořadí dodá model). Rozbalení a fokus drží strom
 * sám; v pořadí Tab je jen jedna položka a šipky chodí po viditelných (`tree-nav.ts`). Výběr
 * worktree hlásí nahoru (`onSelect`), bez něj Enter worktree jen rozbalí. Relace a karty otevírá `nav`.
 */
export default function WorktreeTree({ worktrees, label, compact = false, selectedId = null, nav, onSelect }: {
  worktrees: LiveWorktree[]; label: string; compact?: boolean; selectedId?: string | null;
  nav?: WorktreeNav; onSelect?: (id: string | null) => void;
}) {
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [focused, setFocused] = useState<string | null>(null);
  const elements = useRef(new Map<string, HTMLLIElement>());
  const items = visibleItems(worktrees, open);
  const stop = tabStop(items, focused);
  const toggle = (id: string, force?: boolean) => setOpen((current) => {
    const next = new Set(current);
    if (force ?? !next.has(id)) next.add(id); else next.delete(id);
    return next;
  });
  const moveTo = (key: string) => { setFocused(key); elements.current.get(key)?.focus(); };
  const activate = (item: TreeItem) => {
    setFocused(item.key);
    if (item.kind === "worktree") {
      if (!onSelect) return toggle(item.worktreeId);
      onSelect(selectedId === item.worktreeId ? null : item.worktreeId);
      if (!open.has(item.worktreeId)) toggle(item.worktreeId, true);
    } else if (item.kind === "card") nav?.onOpenCard({ workspace: item.worktreeId, nodeId: item.targetId });
    else {
      const session = worktrees.find((w) => w.id === item.worktreeId)?.sessions.find((s) => s.id === item.targetId);
      if (session?.source === "assistant") nav?.onOpenSession(session.id);
    }
  };
  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const current = (event.target as HTMLElement).closest<HTMLElement>("[data-tree-key]")?.dataset.treeKey;
    const move = current ? treeKey(items, current, event.key, open) : null;
    if (!move) return;
    event.preventDefault();
    if (move.expand) toggle(move.expand, true);
    if (move.collapse) toggle(move.collapse, false);
    if (move.focus) moveTo(move.focus);
    if (move.activate) activate(move.activate);
  };
  const register = (key: string) => (element: HTMLLIElement | null) => { if (element) elements.current.set(key, element); else elements.current.delete(key); };
  return <ul role="tree" aria-label={label} className={"live-status__tree" + (compact ? " live-status__tree--compact" : "")} onKeyDown={onKeyDown}>
    {worktrees.map((worktree) => <WorktreeRow key={worktree.id} worktree={worktree} expanded={open.has(worktree.id)} selected={selectedId === worktree.id} nav={nav}
      focus={{ tabStop: stop, register, onActivate: activate }} onToggle={() => toggle(worktree.id)}/>)}
  </ul>;
}
