import { useState } from "react";
import "../styles/live-status.css";
import type { LiveWorktree } from "../logic/live-model";
import WorktreeRow, { type WorktreeActions } from "./WorktreeRow";

/**
 * Strom worktree (`role="tree"`): nejživější nahoře (pořadí dodá model). Rozbalení drží strom sám,
 * výběr worktree hlásí nahoru; klik na worktree prostor nepřepíná, to dělá až tlačítko v akcích.
 */
export default function WorktreeTree({ worktrees, label, compact = false, selectedId = null, actions, onSelect }: {
  worktrees: LiveWorktree[]; label: string; compact?: boolean; selectedId?: string | null;
  actions?: WorktreeActions; onSelect?: (id: string | null) => void;
}) {
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const toggle = (id: string) => setOpen((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  return <ul role="tree" aria-label={label} className={"live-status__tree" + (compact ? " live-status__tree--compact" : "")}>
    {worktrees.map((worktree) => <WorktreeRow key={worktree.id} worktree={worktree} expanded={open.has(worktree.id)} selected={selectedId === worktree.id} actions={actions}
      onToggle={() => toggle(worktree.id)}
      onSelect={onSelect ? () => { onSelect(selectedId === worktree.id ? null : worktree.id); if (!open.has(worktree.id)) toggle(worktree.id); } : undefined}/>)}
  </ul>;
}
