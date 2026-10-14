import { useState } from "react";
import { countsLine, type LiveWorktree, type LiveCounts } from "@/project/architecture-editor/live-status/logic/live-model";
import WorktreeTree from "@/project/architecture-editor/live-status/components/WorktreeTree";
import type { WorktreeNav } from "@/project/architecture-editor/live-status/components/WorktreeRow";

/**
 * Práce na doméně v kartě přehledu: věta s počty, která rozbalí stěsnaný strom worktree (karty
 * a relace v něm jdou otevřít). Klidná doména nabídne „Nový worktree“; zastaralý údaj nese čas.
 */
export default function DomainWork({ counts, worktrees, label, stale, nav, onCreateWorktree }: {
  counts: LiveCounts; worktrees: LiveWorktree[]; label: string; stale: string; nav?: WorktreeNav; onCreateWorktree: () => void;
}) {
  const [open, setOpen] = useState(false);
  const note = stale && <small className="arch-landing__stale">{stale}</small>;
  if (!counts.total) return <div className="arch-landing__work arch-landing__work--idle">
    <p className="arch-landing__work-text">Na této doméně se teď nepracuje.</p>
    {note}
    <button type="button" className="arch-landing__quiet arch-landing__work-new" data-testid="landing-new-worktree" onClick={onCreateWorktree}>Nový worktree</button>
  </div>;
  return <div className="arch-landing__work">
    <button type="button" className="arch-landing__work-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
      <span aria-hidden="true">{open ? "▾" : "▸"}</span> {countsLine(counts)}
    </button>
    {note}
    {open && <WorktreeTree worktrees={worktrees} label={label} compact nav={nav}/>}
  </div>;
}
